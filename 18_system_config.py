from main import client, db_id
from main import db_collection_id18
from appwrite.services.databases import Databases

db = Databases(client)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="email_notifications",
    required=False,
    default=True
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="sms_notifications",
    required=False,
    default=False
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="maintenance_mode",
    required=False,
    default=False
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="auto_backup",
    required=False,
    default=True
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="two_factor_auth",
    required=False,
    default=True
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="session_timeout",
    required=False,
    min=5,
    max=1440,
    default=30
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="session_idle_warning_minutes",
    required=False,
    min=1,
    max=120,
    default=5
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="max_concurrent_sessions",
    required=False,
    min=1,
    max=20,
    default=3
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="force_logout_on_password_change",
    required=False,
    default=True
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="password_min_length",
    required=False,
    min=6,
    max=32,
    default=8
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="max_upload_size",
    required=False,
    min=1,
    max=500,
    default=50
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="api_base_url",
    size=500,
    required=False,
    default="https://api.farmestates.com"
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="webhook_url",
    size=500,
    required=False,
    default="https://hooks.farmestates.com"
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="api_rate_limit",
    required=False,
    min=10,
    max=10000,
    default=1000
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="sensor_ingest_api_key",
    size=255,
    required=False,
    default=""
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="currency_code",
    elements=["GHS", "USD", "EUR", "GBP"],
    required=False,
    default="GHS"
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="currency_symbol",
    size=10,
    required=False,
    default="GHS"
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="google_maps_enabled",
    required=False,
    default=False
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="google_maps_api_key",
    size=500,
    required=False,
    default=""
)

result = db.create_float_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="google_maps_default_lat",
    required=False,
    min=-90,
    max=90,
    default=5.6037
)

result = db.create_float_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="google_maps_default_lng",
    required=False,
    min=-180,
    max=180,
    default=-0.1870
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="google_maps_default_zoom",
    required=False,
    min=1,
    max=22,
    default=10
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="fulfillment_push_alerts",
    required=False,
    default=True
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="fulfillment_dock_escalations",
    required=False,
    default=True
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="fulfillment_auto_reorder_drafts",
    required=False,
    default=False
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="qa_require_dual_approval",
    required=False,
    default=True
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="qa_inspection_alerts",
    required=False,
    default=True
)

result = db.create_boolean_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="qa_auto_export_reports",
    required=False,
    default=False
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="updated_at",
    required=False
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id18,
    key="updated_by",
    size=225,
    required=False,
    default="system"
)
