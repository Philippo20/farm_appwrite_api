from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases

from main import client, db_collection_id27, db_id

db = Databases(client)


def ensure_collection():
    try:
        db.get_collection(database_id=db_id, collection_id=db_collection_id27)
    except AppwriteException:
        db.create_collection(
            database_id=db_id,
            collection_id=db_collection_id27,
            name="Caretaker settings",
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

safe_create(
    "user_id",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="user_id", size=225, required=True
    ),
)
safe_create(
    "task_reminders",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="task_reminders", required=False, default=True
    ),
)
safe_create(
    "anomaly_alerts",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="anomaly_alerts", required=False, default=True
    ),
)
safe_create(
    "weather_warnings",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="weather_warnings", required=False, default=True
    ),
)
safe_create(
    "chat_notifications",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="chat_notifications", required=False, default=True
    ),
)
safe_create(
    "email_summaries",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="email_summaries", required=False, default=False
    ),
)
safe_create(
    "sound_alerts",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="sound_alerts", required=False, default=True
    ),
)
safe_create(
    "offline_mode",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="offline_mode", required=False, default=True
    ),
)
safe_create(
    "auto_sync_records",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="auto_sync_records", required=False, default=True
    ),
)
safe_create(
    "compact_cards",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="compact_cards", required=False, default=False
    ),
)
safe_create(
    "biometric_lock",
    lambda: db.create_boolean_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="biometric_lock", required=False, default=False
    ),
)
safe_create(
    "shift_start",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="shift_start", size=32, required=False, default="06:00 AM"
    ),
)
safe_create(
    "reminder_lead_time",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="reminder_lead_time", size=32, required=False, default="30 minutes"
    ),
)
safe_create(
    "default_landing_page",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="default_landing_page", size=64, required=False, default="Dashboard"
    ),
)
safe_create(
    "theme_mode",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="theme_mode", size=16, required=False, default="system"
    ),
)
safe_create(
    "updated_at",
    lambda: db.create_datetime_attribute(
        database_id=db_id, collection_id=db_collection_id27, key="updated_at", required=False
    ),
)
