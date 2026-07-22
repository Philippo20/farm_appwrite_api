from main import client, db_id
from main import db_collection_id22
from appwrite.services.databases import Databases

db = Databases(client)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="request_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="farm_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="farm_name",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="requested_by_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="requested_by_name",
    size=225,
    required=True
)

result = db.create_float_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="amount",
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="currency",
    size=12,
    required=False,
    default="GHS"
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="purpose",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="description",
    size=1000,
    required=False,
    default=""
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="category",
    elements=["Operations", "Inputs", "Maintenance", "Capital", "Labour", "Transport", "Other"],
    required=True
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="priority",
    elements=["High", "Medium", "Low"],
    required=True
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="status",
    elements=["Pending", "Approved", "Rejected", "Disbursed"],
    required=True
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="request_date",
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="approved_by_id",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="approved_by_name",
    size=225,
    required=False,
    default=""
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="approved_at",
    required=False
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="decision_notes",
    size=1000,
    required=False,
    default=""
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id22,
    key="updated_at",
    required=True
)
