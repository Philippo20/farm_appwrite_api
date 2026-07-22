from main import client, db_id
from main import db_collection_id20
from appwrite.services.databases import Databases

db = Databases(client)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="movement_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="item_id",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="item_name",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="farm_id",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="farm_name",
    size=225,
    required=False,
    default="Unassigned Farm"
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="movement_type",
    elements=["stock_in", "stock_out", "adjustment"],
    required=True
)

result = db.create_float_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="quantity",
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="unit",
    size=50,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="actor",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="note",
    size=1000,
    required=False,
    default=""
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id20,
    key="timestamp",
    required=True
)
