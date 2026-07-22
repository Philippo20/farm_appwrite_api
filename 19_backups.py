from main import client, db_id
from main import db_collection_id19
from appwrite.services.databases import Databases

db = Databases(client)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="file_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="file_name",
    size=500,
    required=True
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="size_bytes",
    required=False,
    min=0,
    default=0
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="collections",
    size=225,
    required=False,
    array=True
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="created_at",
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="notes",
    size=1000,
    required=False,
    default=""
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="backup_type",
    elements=["Manual", "Automated"],
    required=False,
    default="Manual"
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="status",
    elements=["Verified", "Pending Review", "Failed"],
    required=False,
    default="Verified"
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="scope",
    size=225,
    required=False,
    default="global"
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="farm",
    size=225,
    required=False,
    default="Global Platform"
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id19,
    key="retention_days",
    required=False,
    min=1,
    max=3650,
    default=90
)
