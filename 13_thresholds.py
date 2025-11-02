from main import client, db_id
from main import db_collection_id13
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id13,
    key= "farmID",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id13,
    key="temperature_max",
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id13,
    key="temperature_min",
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id13,
    key="ph_min",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id13,
    key="ph_max",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id13,
    key="ec_max",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id13,
    key="humidity_max",
    required= False,
    min=0.0
)