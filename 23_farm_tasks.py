from main import client, db_id
from main import db_collection_id23
from appwrite.services.databases import Databases

db = Databases(client)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="task_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="farm_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="farm_name",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="title",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="description",
    size=1000,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="manager_comment",
    size=2000,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="caretaker_comment",
    size=2000,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="assigned_to_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="assigned_to_name",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="assigned_by_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="assigned_by_name",
    size=225,
    required=True
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="priority",
    elements=["High", "Medium", "Low"],
    required=True
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="status",
    elements=["Not Started", "Started", "Pending", "In Progress", "Completed", "Cancelled"],
    required=True
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="due_date",
    required=False
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="created_at",
    required=True
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id23,
    key="updated_at",
    required=True
)
