from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases
from main import client, db_collection_id32, db_id

db = Databases(client)

def safe_create(label, create_fn):
    try:
        create_fn()
        print(f"created {label}")
    except AppwriteException as error:
        if getattr(error, "code", None) == 409 or "already exists" in str(error).lower():
            print(f"exists {label}")
            return
        raise

try:
    db.get_collection(database_id=db_id, collection_id=db_collection_id32)
except AppwriteException:
    db.create_collection(database_id=db_id, collection_id=db_collection_id32, name="Traceability Promotions")

safe_create("promotion_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id32, key="promotion_id", size=225, required=True))
safe_create("title", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id32, key="title", size=225, required=True))
safe_create("message", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id32, key="message", size=2000, required=True))
safe_create("image_url", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id32, key="image_url", size=1000, required=False, default=""))
safe_create("destination_url", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id32, key="destination_url", size=1000, required=False, default=""))
safe_create("target_batch_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id32, key="target_batch_id", size=225, required=False, default=""))
safe_create("target_region", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id32, key="target_region", size=225, required=False, default=""))
safe_create("created_by", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id32, key="created_by", size=225, required=False, default="system"))
safe_create("status", lambda: db.create_enum_attribute(database_id=db_id, collection_id=db_collection_id32, key="status", elements=["draft", "active", "paused", "expired"], required=True))
safe_create("priority", lambda: db.create_integer_attribute(database_id=db_id, collection_id=db_collection_id32, key="priority", required=False, default=0, min=0))
safe_create("impressions", lambda: db.create_integer_attribute(database_id=db_id, collection_id=db_collection_id32, key="impressions", required=False, default=0, min=0))
safe_create("clicks", lambda: db.create_integer_attribute(database_id=db_id, collection_id=db_collection_id32, key="clicks", required=False, default=0, min=0))
safe_create("start_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id32, key="start_at", required=False))
safe_create("end_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id32, key="end_at", required=False))
safe_create("created_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id32, key="created_at", required=False))
safe_create("updated_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id32, key="updated_at", required=False))
