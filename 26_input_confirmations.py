from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases

from main import client, db_collection_id26, db_id

db = Databases(client)


def ensure_collection():
    try:
        db.get_collection(database_id=db_id, collection_id=db_collection_id26)
    except AppwriteException:
        db.create_collection(
            database_id=db_id,
            collection_id=db_collection_id26,
            name="Input confirmations",
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
    "input_id",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="input_id",
        size=225,
        required=True,
    ),
)
safe_create(
    "farm_id",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="farm_id",
        size=225,
        required=True,
    ),
)
safe_create(
    "farm_name",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="farm_name",
        size=225,
        required=True,
    ),
)
safe_create(
    "item",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="item",
        size=225,
        required=True,
    ),
)
safe_create(
    "quantity",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="quantity",
        size=225,
        required=True,
    ),
)
safe_create(
    "requested_by_id",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="requested_by_id",
        size=225,
        required=True,
    ),
)
safe_create(
    "requested_by_name",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="requested_by_name",
        size=225,
        required=True,
    ),
)
safe_create(
    "caretaker_id",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="caretaker_id",
        size=225,
        required=True,
    ),
)
safe_create(
    "caretaker_name",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="caretaker_name",
        size=225,
        required=True,
    ),
)
safe_create(
    "notes",
    lambda: db.create_string_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="notes",
        size=2000,
        required=False,
        default="",
    ),
)
safe_create(
    "status",
    lambda: db.create_enum_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="status",
        elements=["Pending", "Received", "Confirmed"],
        required=True,
    ),
)
safe_create(
    "requested_at",
    lambda: db.create_datetime_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="requested_at",
        required=False,
    ),
)
safe_create(
    "received_at",
    lambda: db.create_datetime_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="received_at",
        required=False,
    ),
)
safe_create(
    "confirmed_at",
    lambda: db.create_datetime_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="confirmed_at",
        required=False,
    ),
)
safe_create(
    "created_at",
    lambda: db.create_datetime_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="created_at",
        required=False,
    ),
)
safe_create(
    "updated_at",
    lambda: db.create_datetime_attribute(
        database_id=db_id,
        collection_id=db_collection_id26,
        key="updated_at",
        required=False,
    ),
)
