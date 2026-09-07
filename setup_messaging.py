"""Run once before deploying the messages API; safe to rerun."""
import os
import time
from appwrite.exception import AppwriteException
from db import db
from main import db_id


def setup():
    collection = os.getenv("APPWRITE_MESSAGES_COLLECTION_ID", "team_messages")
    try:
        db.create_collection(database_id=db_id, collection_id=collection,
                             name="Team Messages", permissions=[], document_security=False)
    except AppwriteException as error:
        if error.code != 409:
            raise
    for key, size in [("conversation_id", 36), ("sender_id", 36), ("recipient_id", 36), ("text", 4000), ("read_at", 40)]:
        try:
            db.create_string_attribute(database_id=db_id, collection_id=collection,
                                        key=key, size=size, required=key != "read_at")
        except AppwriteException as error:
            if error.code != 409:
                raise
    for _ in range(60):
        attrs = db.list_attributes(database_id=db_id, collection_id=collection)["attributes"]
        if all(item["status"] == "available" for item in attrs) and len(attrs) >= 5:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Message attributes are not ready; rerun setup after checking Appwrite.")
    for key in ("conversation_id", "sender_id", "recipient_id"):
        try:
            db.create_index(database_id=db_id, collection_id=collection,
                            key=key, type="key", attributes=[key])
        except AppwriteException as error:
            if error.code != 409:
                raise
    print("Message collection configured. Deploy the API and Flutter client.")


if __name__ == "__main__":
    setup()
