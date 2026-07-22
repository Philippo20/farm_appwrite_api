from main import client, db_id
from main import db_collection_id21
from appwrite.services.databases import Databases

db = Databases(client)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="sensor_id",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="serial_number",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="farmID",
    size=225,
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="farm_name",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="sensortype",
    size=100,
    required=False,
    default=""
)

result = db.create_float_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="value",
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="unit",
    size=50,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="status",
    size=50,
    required=False,
    default="Active"
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="timestamp",
    required=True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id21,
    key="source",
    size=50,
    required=False,
    default="ingest"
)
