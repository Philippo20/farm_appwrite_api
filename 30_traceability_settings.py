from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases
from main import client, db_collection_id30, db_id

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
    db.get_collection(database_id=db_id, collection_id=db_collection_id30)
except AppwriteException:
    db.create_collection(database_id=db_id, collection_id=db_collection_id30, name="Traceability Settings")

safe_create("config_id", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="config_id", size=80, required=True))
safe_create("public_site_url", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="public_site_url", size=500, required=False, default="https://app.farmestates.farm"))
safe_create("brand_name", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="brand_name", size=160, required=False, default="Farm Estates Ltd"))
safe_create("headline", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="headline", size=500, required=False, default="Know where your food comes from"))
safe_create("support_email", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="support_email", size=225, required=False, default=""))
safe_create("primary_color", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="primary_color", size=20, required=False, default="#4CAF50"))
safe_create("secondary_color", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="secondary_color", size=20, required=False, default="#29B6F6"))
safe_create("logo_url", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="logo_url", size=1000, required=False, default=""))
safe_create("privacy_notice_url", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="privacy_notice_url", size=1000, required=False, default=""))
safe_create("updated_by", lambda: db.create_string_attribute(database_id=db_id, collection_id=db_collection_id30, key="updated_by", size=225, required=False, default="system"))
safe_create("lookup_enabled", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="lookup_enabled", required=False, default=True))
safe_create("maintenance_mode", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="maintenance_mode", required=False, default=False))
safe_create("show_farm", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="show_farm", required=False, default=True))
safe_create("show_location", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="show_location", required=False, default=True))
safe_create("show_dates", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="show_dates", required=False, default=True))
safe_create("show_quality", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="show_quality", required=False, default=True))
safe_create("show_journey", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="show_journey", required=False, default=True))
safe_create("analytics_enabled", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="analytics_enabled", required=False, default=True))
safe_create("promotions_enabled", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="promotions_enabled", required=False, default=True))
safe_create("feedback_enabled", lambda: db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id30, key="feedback_enabled", required=False, default=True))
safe_create("retention_days", lambda: db.create_integer_attribute(database_id=db_id, collection_id=db_collection_id30, key="retention_days", required=False, default=365, min=30, max=1825))
safe_create("updated_at", lambda: db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id30, key="updated_at", required=True))
