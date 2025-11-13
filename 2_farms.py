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
    elements=["active", "inactive"],
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