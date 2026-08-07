from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases

from main import client, db_collection_id29, db_id

db = Databases(client)


def ensure_collection():
    try:
        db.get_collection(database_id=db_id, collection_id=db_collection_id29)
    except AppwriteException:
        db.create_collection(
            database_id=db_id,
            collection_id=db_collection_id29,
            name="Off-taker update requests",
        )


def safe_create(label, create_fn):
    try:
        create_fn()
        print(f"created {label}")
    except AppwriteException as error:
        if "already exists" in str(error).lower() or getattr(error, "code", None) == 409:
            print(f"exists {label}")
            return
        raise


ensure_collection()

safe_create("off_taker_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id29, key="off_taker_id", size=225, required=True))
safe_create("requested_by_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id29, key="requested_by_id", size=225, required=True))
safe_create("requested_by_name", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id29, key="requested_by_name", size=225, required=True))
safe_create("reason", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id29, key="reason", size=4000, required=True))
safe_create("proposed_data", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id29, key="proposed_data", size=4000, required=True))
safe_create("reviewed_by_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id29, key="reviewed_by_id", size=225, required=False, default=""))
safe_create("reviewed_by_name", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id29, key="reviewed_by_name", size=225, required=False, default=""))
safe_create("review_notes", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id29, key="review_notes", size=4000, required=False, default=""))
safe_create("status", lambda: db.create_enum_attribute(database_id=db_id, collection_id=db_collection_id29, key="status", elements=["Pending", "Approved", "Rejected"], required=True))
safe_create("requested_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id29, key="requested_at", required=False))
safe_create("reviewed_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id29, key="reviewed_at", required=False))
