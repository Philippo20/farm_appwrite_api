from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases
from main import client, db_collection_id31, db_id

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
    db.get_collection(database_id=db_id, collection_id=db_collection_id31)
except AppwriteException:
    db.create_collection(database_id=db_id, collection_id=db_collection_id31, name="Batch Traceability")

safe_create("trace_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="trace_id", size=225, required=True))
safe_create("batch_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="batch_id", size=225, required=True))
safe_create("batch_number", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="batch_number", size=225, required=True))
safe_create("public_token", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="public_token", size=225, required=True))
safe_create("product_name", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="product_name", size=225, required=False, default=""))
safe_create("variety", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="variety", size=225, required=False, default=""))
safe_create("farm_name", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="farm_name", size=225, required=False, default=""))
safe_create("farm_region", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="farm_region", size=225, required=False, default=""))
safe_create("packaging_label", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="packaging_label", size=225, required=False, default=""))
safe_create("quality_status", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="quality_status", size=80, required=False, default="Verified"))
safe_create("public_message", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="public_message", size=2000, required=False, default=""))
safe_create("created_by", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id31, key="created_by", size=225, required=False, default="system"))
safe_create("published", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id31, key="published", required=False, default=False))
safe_create("scan_count", lambda: db.create_integer_attribute(database_id=db_id, collection_id=db_collection_id31, key="scan_count", required=False, default=0, min=0))
safe_create("recall_status", lambda: db.create_enum_attribute(database_id=db_id, collection_id=db_collection_id31, key="recall_status", elements=["none", "advisory", "recalled"], required=False, default="none"))
safe_create("published_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id31, key="published_at", required=False))
safe_create("created_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id31, key="created_at", required=False))
safe_create("updated_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id31, key="updated_at", required=False))
