from main import client, db_id
from main import db_collection_id15
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id15,
    key= "farmID",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id15,
    key="stage_name",
    elements=["germination", "vegetative", "flowering", "harvest"],
    required= True
)

result = db.create_boolean_attribute(
    database_id= db_id,
    collection_id= db_collection_id15,
    key="started",
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id15,
    key="start_time",
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id15,
    key="end_time",
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id15,
    key= "created_by",
    size= 225,
    required= True
)