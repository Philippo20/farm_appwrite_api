from main import client, db_id
from main import db_collection_id16
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key= "crop_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key= "crop_image",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key= "variety_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key= "plant_duration",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="harvesting_weight",
    required= True,
    min=0.0
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key= "company",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="sprouting_ratio",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="ec_level_min",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="ec_level_max",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="ph_level_min",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="ph_level_max",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="temp_min",
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="temp_max",
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="humidity_min",
    required= True,
    min=0.0
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key="humidity_max",
    required= True,
    min=0.0
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id16,
    key= "created_by",
    size= 225,
    required= True
)   