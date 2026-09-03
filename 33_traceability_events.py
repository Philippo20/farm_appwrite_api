from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases
from main import client, db_collection_id33, db_id

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
    db.get_collection(database_id=db_id, collection_id=db_collection_id33)
except AppwriteException:
    db.create_collection(database_id=db_id, collection_id=db_collection_id33, name="Traceability Events")

safe_create("event_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="event_id", size=225, required=True))
safe_create("trace_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="trace_id", size=225, required=False, default=""))
safe_create("batch_number", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="batch_number", size=225, required=False, default=""))
safe_create("promotion_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="promotion_id", size=225, required=False, default=""))
safe_create("anonymous_session", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="anonymous_session", size=225, required=False, default=""))
safe_create("ip_hash", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="ip_hash", size=225, required=False, default=""))
safe_create("ip_masked", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="ip_masked", size=120, required=False, default=""))
safe_create("country", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="country", size=120, required=False, default=""))
safe_create("region", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="region", size=160, required=False, default=""))
safe_create("city", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="city", size=160, required=False, default=""))
safe_create("device_type", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="device_type", size=80, required=False, default="unknown"))
safe_create("browser", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="browser", size=120, required=False, default="Unknown"))
safe_create("operating_system", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="operating_system", size=120, required=False, default="Unknown"))
safe_create("timezone", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="timezone", size=120, required=False, default=""))
safe_create("isp", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="isp", size=225, required=False, default=""))
safe_create("latitude", lambda: db.create_float_attribute(database_id=db_id, collection_id=db_collection_id33, key="latitude", required=False, default=0.0, min=-90.0, max=90.0))
safe_create("longitude", lambda: db.create_float_attribute(database_id=db_id, collection_id=db_collection_id33, key="longitude", required=False, default=0.0, min=-180.0, max=180.0))
safe_create("referrer", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="referrer", size=1000, required=False, default=""))
safe_create("user_agent", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id33, key="user_agent", size=1000, required=False, default=""))
safe_create("event_type", lambda: db.create_enum_attribute(database_id=db_id, collection_id=db_collection_id33, key="event_type", elements=["page_view", "lookup_success", "lookup_failed", "promotion_impression", "promotion_click"], required=True))
safe_create("occurred_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id33, key="occurred_at", required=True))
