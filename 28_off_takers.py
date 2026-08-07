from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases

from main import client, db_collection_id28, db_id

db = Databases(client)


def ensure_collection():
    try:
        db.get_collection(database_id=db_id, collection_id=db_collection_id28)
    except AppwriteException:
        db.create_collection(
            database_id=db_id,
            collection_id=db_collection_id28,
            name="Off-takers",
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
    "name",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id28, key="name", size=225, required=True
    ),
)
safe_create(
    "business_type",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id28, key="business_type", size=225, required=False
    ),
)
safe_create(
    "contact_person",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id28, key="contact_person", size=225, required=False
    ),
)
safe_create(
    "phone",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id28, key="phone", size=50, required=False
    ),
)
safe_create(
    "email",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id28, key="email", size=254, required=False
    ),
)
safe_create(
    "location",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id28, key="location", size=225, required=False
    ),
)
safe_create(
    "status",
    lambda: db.create_enum_attribute(
        database_id=db_id,
        collection_id=db_collection_id28,
        key="status",
        elements=["Active", "Inactive", "Prospect"],
        required=True,
    ),
)
safe_create(
    "notes",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id28, key="notes", size=2000, required=False
    ),
)
safe_create(
    "created_by",
    lambda: db.create_string_attribute(
        database_id=db_id, collection_id=db_collection_id28, key="created_by", size=225, required=False
    ),
)
