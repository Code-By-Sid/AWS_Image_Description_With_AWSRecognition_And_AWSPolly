from flask import Flask, render_template, request, redirect
import requests
import base64

app = Flask(__name__)

# ==========================================
# API Gateway URL
# ==========================================

API = "https://mllr221c1j.execute-api.ap-south-1.amazonaws.com/default"


# ==========================================
# Home Page
# ==========================================

@app.route("/")
def home():

    try:

        response = requests.get(

            API + "/images"

        )

        data = response.json()

        images = data.get("images", [])

    except Exception as e:

        print(e)

        images = []

    return render_template(

        "index.html",

        images=images

    )


# ==========================================
# Upload Image
# ==========================================

@app.route("/upload", methods=["POST"])
def upload():

    file = request.files["image"]

    image_bytes = file.read()

    image_base64 = base64.b64encode(

        image_bytes

    ).decode("utf-8")

    body = {

        "filename": file.filename,

        "image": image_base64

    }

    requests.post(

        API + "/upload",

        json=body

    )

    return redirect("/")


# ==========================================
# Run Flask
# ==========================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=4000,

        debug=True

    )