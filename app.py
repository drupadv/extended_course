import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-in-env")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
EXTENDED_COLLECTION_NAME = os.getenv("MONGO_EXTENDED_COLLECTION_NAME", "extended_courses")
CURRENTALLOCATION_COLLECTION_NAME = os.getenv("MONGO_CURRENTALLOCATION_COLLECTION_NAME", "currentallocation")
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "5000"))
APP_DEBUG = os.getenv("APP_DEBUG", "False").lower() == "true"

if not MONGO_URI:
    raise ValueError("MONGO_URI is not set in the .env file")

if not MONGO_DB_NAME:
    raise ValueError("MONGO_DB_NAME is not set in the .env file")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

extended_courses_collection = db[EXTENDED_COLLECTION_NAME]
currentallocation_collection = db[CURRENTALLOCATION_COLLECTION_NAME]


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        course_tag = request.form.get("course_tag", "").strip()

        if not course_tag:
            flash("Course tag is required.", "error")
            return redirect(url_for("index"))

        try:
            # Validation 1:
            # Only allow insert into extended_courses if tag exists in currentallocation.tag
            currentallocation_match = currentallocation_collection.find_one({"tag": course_tag})

            if not currentallocation_match:
                flash(
                    "The course entry is not present in currentallocation collection. Please check MongoDB",
                    "error"
                )
                return redirect(url_for("index"))

            # Validation 2:
            # If same course tag already exists in extended_courses, delete old entry/entries
            extended_courses_collection.delete_many({"course_tag": course_tag})

            # Insert fresh document
            document = {
                "course_tag": course_tag,
                "submitted_at": datetime.now(timezone.utc)
            }

            extended_courses_collection.insert_one(document)

            flash(f"Course tag '{course_tag}' was already present. Updated old entry.", "success")

        except PyMongoError as exc:
            flash(f"Failed to submit course tag. Error: {exc}", "error")

        return redirect(url_for("index"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)