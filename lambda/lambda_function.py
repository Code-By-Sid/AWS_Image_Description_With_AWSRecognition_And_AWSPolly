import json
import boto3
import base64
import uuid
from datetime import datetime
from decimal import Decimal

# ==========================================
# AWS Clients
# ==========================================

s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")
polly = boto3.client("polly")
dynamodb = boto3.resource("dynamodb")

# ==========================================
# DynamoDB Table
# ==========================================

table = dynamodb.Table("ImageDescriptions")

# ==========================================
# Configuration
# ==========================================

IMAGE_BUCKET = "image-description-buc-ket"
AUDIO_BUCKET = "image-description-audio"

VOICE_ID = "Joanna"

# ==========================================
# JSON Encoder
# ==========================================

def decimal_default(obj):

    if isinstance(obj, Decimal):
        return float(obj)

    raise TypeError


# ==========================================
# Response
# ==========================================

def response(status, body):

    return {

        "statusCode": status,

        "headers": {

            "Content-Type": "application/json",

            "Access-Control-Allow-Origin": "*"

        },

        "body": json.dumps(

            body,

            default=decimal_default

        )

    }


# ==========================================
# Lambda Handler
# ==========================================

def lambda_handler(event, context):

    try:

        method = event["requestContext"]["http"]["method"]

        path = event["rawPath"]

        print(method)

        print(path)

        # ==========================================
        # POST /upload
        # ==========================================

        if method == "POST" and path.endswith("/upload"):

            body = json.loads(event["body"])

            filename = body["filename"]

            image_data = body["image"]

            # Remove Base64 Header if present

            if "," in image_data:

                image_data = image_data.split(",")[1]

            image_bytes = base64.b64decode(image_data)

            # Upload Image

            s3.put_object(

                Bucket=IMAGE_BUCKET,

                Key=filename,

                Body=image_bytes,

                ContentType="image/jpeg"

            )

            print("Image Uploaded")

            image_url = f"https://{IMAGE_BUCKET}.s3.amazonaws.com/{filename}"

            # ==========================================
            # Amazon Rekognition
            # ==========================================

            print("Detecting Labels...")

            rekognition_response = rekognition.detect_labels(

                Image={

                    "S3Object": {

                        "Bucket": IMAGE_BUCKET,

                        "Name": filename

                    }

                },

                MaxLabels=10,

                MinConfidence=75

            )

            labels = []

            highest_confidence = Decimal("0")

            primary_label = "Unknown"

            for label in rekognition_response["Labels"]:

                confidence = Decimal(
                    str(round(label["Confidence"], 2))
                )

                labels.append(

                    {

                        "Name": label["Name"],

                        "Confidence": confidence

                    }

                )

                if confidence > highest_confidence:

                    highest_confidence = confidence

                    primary_label = label["Name"]

            print(labels)

            # ==========================================
            # Generate Description
            # ==========================================

            label_names = [

                label["Name"]

                for label in labels

            ]

            if len(label_names) == 1:

                description = (

                    f"This image contains {label_names[0]}. "

                    f"The primary object detected is "

                    f"{primary_label} with a confidence of "

                    f"{highest_confidence} percent."

                )

            else:

                description = (

                    "This image contains "

                    + ", ".join(label_names[:-1])

                    + " and "

                    + label_names[-1]

                    + ". "

                    + "The primary object detected is "

                    + primary_label

                    + " with a confidence of "

                    + str(highest_confidence)

                    + " percent."

                )

            print(description)

            # ==========================================
            # Amazon Polly
            # ==========================================

            print("Generating MP3...")

            polly_response = polly.synthesize_speech(

                Text=description,

                OutputFormat="mp3",

                VoiceId=VOICE_ID

            )

            audio_stream = polly_response["AudioStream"].read()

            mp3_name = filename.rsplit(".", 1)[0] + ".mp3"

            s3.put_object(

                Bucket=AUDIO_BUCKET,

                Key=mp3_name,

                Body=audio_stream,

                ContentType="audio/mpeg"

            )

            print("MP3 Uploaded")

            audio_url = (

                f"https://{AUDIO_BUCKET}.s3.amazonaws.com/{mp3_name}"

            )
            # ==========================================
            # Store in DynamoDB
            # ==========================================

            item = {

                "ImageId": str(uuid.uuid4()),

                "ImageName": filename,

                "ImageURL": image_url,

                "AudioURL": audio_url,

                "Description": description,

                "PrimaryLabel": primary_label,

                "HighestConfidence": highest_confidence,

                "Labels": labels,

                "Timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            }

            table.put_item(

                Item=item

            )

            print("Stored Successfully")

            # ==========================================
            # Convert Decimal → Float for API Response
            # ==========================================

            response_labels = []

            for label in labels:

                response_labels.append(

                    {

                        "Name": label["Name"],

                        "Confidence": float(label["Confidence"])

                    }

                )

            return response(

                200,

                {

                    "message": "Image Uploaded Successfully",

                    "imageURL": image_url,

                    "audioURL": audio_url,

                    "description": description,

                    "primaryLabel": primary_label,

                    "highestConfidence": float(highest_confidence),

                    "labels": response_labels

                }

            )

        # ==========================================
        # GET /images
        # ==========================================

        elif method == "GET" and path.endswith("/images"):

            db = table.scan()

            items = db.get("Items", [])

            images = []

            for item in items:

                converted_labels = []

                for label in item["Labels"]:

                    converted_labels.append(

                        {

                            "Name": label["Name"],

                            "Confidence": float(label["Confidence"])

                        }

                    )

                images.append(

                    {

                        "imageId": item["ImageId"],

                        "imageName": item["ImageName"],

                        "imageURL": item["ImageURL"],

                        "audioURL": item["AudioURL"],

                        "description": item["Description"],

                        "primaryLabel": item["PrimaryLabel"],

                        "highestConfidence": float(
                            item["HighestConfidence"]
                        ),

                        "labels": converted_labels,

                        "timestamp": item["Timestamp"]

                    }

                )

            return response(

                200,

                {

                    "images": images

                }

            )

        # ==========================================
        # Invalid Route
        # ==========================================

        else:

            return response(

                404,

                {

                    "message": "Invalid API Route"

                }

            )

    except Exception as e:

        print("ERROR :", str(e))

        return response(

            500,

            {

                "error": str(e)

            }

        )