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


def is_extend_true(value):
    """
    Accept extend values stored as:
    - True
    - False
    - "true"
    - "false"
    - "True"
    - "False"
    - " TRUE "
    - " FALSE "
    Returns True only when the normalized value is true.
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() == "true"

    return False


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        course_tag = request.form.get("course_tag", "").strip()

        if not course_tag:
            flash("Course tag is required.", "error")
            return redirect(url_for("index"))

        try:
            currentallocation_match = currentallocation_collection.find_one({"tag": course_tag})

            if not currentallocation_match:
                flash(
                    "The course entry is not present in currentallocation collection. Please check MongoDB",
                    "error"
                )
                return redirect(url_for("index"))

            existing_entry = extended_courses_collection.find_one({"course_tag": course_tag})

            extended_courses_collection.delete_many({"course_tag": course_tag})

            document = {
                "course_tag": course_tag,
                "submitted_at": datetime.now(timezone.utc)
            }

            extended_courses_collection.insert_one(document)

            if existing_entry:
                flash(
                    f"Course tag '{course_tag}' already existed. Old entry removed and new entry added.",
                    "success"
                )
            else:
                flash(f"Course tag '{course_tag}' submitted successfully.", "success")

        except PyMongoError as exc:
            flash(f"Failed to submit course tag. Error: {exc}", "error")

        return redirect(url_for("index"))

    return render_template("index.html")


@app.route("/verify-extensions", methods=["GET", "POST"])
def verify_extensions():
    verified = False
    total_source_tags = 0
    marked_true_count = 0
    missed_count = 0
    marked_true_tags = []
    missed_tags = []

    if request.method == "POST":
        try:
            source_docs = list(
                extended_courses_collection.find(
                    {},
                    {"_id": 0, "course_tag": 1, "submitted_at": 1}
                )
            )

            unique_tags = []
            seen = set()

            for doc in source_docs:
                course_tag = str(doc.get("course_tag", "")).strip()
                if course_tag and course_tag not in seen:
                    seen.add(course_tag)
                    unique_tags.append(course_tag)

            total_source_tags = len(unique_tags)

            for course_tag in unique_tags:
                current_doc = currentallocation_collection.find_one(
                    {"tag": course_tag},
                    {"_id": 0, "tag": 1, "extend": 1}
                )

                extend_value = current_doc.get("extend") if current_doc else None

                if current_doc and is_extend_true(extend_value):
                    marked_true_tags.append(
                        {
                            "course_tag": course_tag,
                            "extend_value": extend_value
                        }
                    )
                else:
                    missed_tags.append(
                        {
                            "course_tag": course_tag,
                            "extend_value": extend_value if current_doc else "not found"
                        }
                    )

            marked_true_count = len(marked_true_tags)
            missed_count = len(missed_tags)
            verified = True

        except PyMongoError as exc:
            flash(f"Failed to verify extensions. Error: {exc}", "error")

    return render_template(
        "verify_extensions.html",
        verified=verified,
        total_source_tags=total_source_tags,
        marked_true_count=marked_true_count,
        missed_count=missed_count,
        marked_true_tags=marked_true_tags,
        missed_tags=missed_tags,
    )


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)