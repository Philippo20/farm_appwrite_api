from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases

from main import client, db_collection_id24, db_id

db = Databases(client)


def ensure_collection():
    try:
        db.get_collection(database_id=db_id, collection_id=db_collection_id24)
    except AppwriteException:
        db.create_collection(
            database_id=db_id,
            collection_id=db_collection_id24,
            name="Farm Records",
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

for key, required in [
    ("record_id", True),
    ("farm_id", True),
    ("farm_name", True),
    ("batch_id", False),
    ("batch_number", False),
    ("record_type", True),
    ("created_by", True),
    ("created_by_name", True),
    ("plant_health", False),
    ("growth_stage", False),
]:
    safe_create(
        key,
        lambda key=key, required=required: db.create_string_attribute(
            database_id=db_id,
            collection_id=db_collection_id24,
            key=key,
            size=225,
            required=required,
            default=None if required else "",
        ),
    )

for key in ["observations", "activities_performed", "issue_description", "notes"]:
    safe_create(
        key,
        lambda key=key: db.create_string_attribute(
            database_id=db_id,
            collection_id=db_collection_id24,
            key=key,
            size=2000,
            required=False,
            default="",
        ),
    )

for key in ["record_date", "created_at", "updated_at"]:
    safe_create(
        key,
        lambda key=key: db.create_datetime_attribute(
            database_id=db_id,
            collection_id=db_collection_id24,
            key=key,
            required=True,
        ),
    )

for key in ["temperature", "humidity", "ph", "ec", "light_intensity"]:
    safe_create(
        key,
        lambda key=key: db.create_float_attribute(
            database_id=db_id,
            collection_id=db_collection_id24,
            key=key,
            required=False,
        ),
    )

safe_create(
    "plant_count",
    lambda: db.create_integer_attribute(
        database_id=db_id,
        collection_id=db_collection_id24,
        key="plant_count",
        required=False,
    ),
)

safe_create(
    "has_issues",
    lambda: db.create_boolean_attribute(
        database_id=db_id,
        collection_id=db_collection_id24,
        key="has_issues",
        required=True,
    ),
)

safe_create(
    "issue_severity",
    lambda: db.create_enum_attribute(
        database_id=db_id,
        collection_id=db_collection_id24,
        key="issue_severity",
        elements=["none", "low", "medium", "high", "critical"],
        required=True,
    ),
)
