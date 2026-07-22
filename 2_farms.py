from main import client, db_id
from main import db_collection_id2
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key= "name",
    size= 225,
    required= True
)


result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="location",
    size=225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="ownerID",
    size=225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="caretakerID",
    size=225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="farm_manager_id",
    size=225,
    required=False,
    default="Unassigned"
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="technician_id",
    size=225,
    required=False,
    default="Unassigned"
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="tier_type",
    elements=["Compact", "Medium", "Mega"],
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="status",
    elements=["Active", "Pending", "Suspended"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="plant_type",
    size=100,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id2,
    key="plant_variety",
    size=100,
    required= True
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id2,
    key="sensor_ingest_api_key",
    size=255,
    required=False,
    default=""
)
