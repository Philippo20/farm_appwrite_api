from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases
from main import client, db_collection_id34, db_id

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
    db.get_collection(database_id=db_id, collection_id=db_collection_id34)
except AppwriteException:
    db.create_collection(database_id=db_id, collection_id=db_collection_id34, name="Traceability Feedback")

safe_create("feedback_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="feedback_id", size=225, required=True))
safe_create("trace_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="trace_id", size=225, required=False, default=""))
safe_create("batch_number", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="batch_number", size=225, required=False, default=""))
safe_create("public_token", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="public_token", size=225, required=False, default=""))
safe_create("feedback_type", lambda: db.create_enum_attribute(database_id=db_id, collection_id=db_collection_id34, key="feedback_type", elements=["feedback", "issue"], required=True))
safe_create("category", lambda: db.create_enum_attribute(database_id=db_id, collection_id=db_collection_id34, key="category", elements=["product_quality", "packaging", "delivery", "traceability", "other"], required=True))
safe_create("rating", lambda: db.create_integer_attribute(database_id=db_id, collection_id=db_collection_id34, key="rating", required=False, default=0, min=0, max=5))
safe_create("message", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="message", size=4000, required=True))
safe_create("contact_name", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="contact_name", size=225, required=False, default=""))
safe_create("contact_email", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="contact_email", size=320, required=False, default=""))
safe_create("consent_to_contact", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id34, key="consent_to_contact", required=False, default=False))
safe_create("anonymous_session", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="anonymous_session", size=225, required=False, default=""))
safe_create("ip_hash", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="ip_hash", size=225, required=False, default=""))
safe_create("ip_masked", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="ip_masked", size=120, required=False, default=""))
safe_create("ip_source", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="ip_source", size=80, required=False, default=""))
safe_create("country", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="country", size=120, required=False, default=""))
safe_create("region", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="region", size=160, required=False, default=""))
safe_create("city", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="city", size=160, required=False, default=""))
safe_create("latitude", lambda: db.create_float_attribute(database_id=db_id, collection_id=db_collection_id34, key="latitude", required=False, default=0.0, min=-90.0, max=90.0))
safe_create("longitude", lambda: db.create_float_attribute(database_id=db_id, collection_id=db_collection_id34, key="longitude", required=False, default=0.0, min=-180.0, max=180.0))
safe_create("timezone", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="timezone", size=120, required=False, default=""))
safe_create("isp", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="isp", size=225, required=False, default=""))
safe_create("device_type", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="device_type", size=80, required=False, default="unknown"))
safe_create("browser", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="browser", size=120, required=False, default="Unknown"))
safe_create("operating_system", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="operating_system", size=120, required=False, default="Unknown"))
safe_create("status", lambda: db.create_enum_attribute(database_id=db_id, collection_id=db_collection_id34, key="status", elements=["new", "reviewing", "resolved", "closed"], required=True))
safe_create("admin_notes", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id34, key="admin_notes", size=4000, required=False, default=""))
safe_create("created_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id34, key="created_at", required=True))
safe_create("updated_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id34, key="updated_at", required=True))
