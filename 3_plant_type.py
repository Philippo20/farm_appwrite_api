from main import client, db_id
from main import db_collection_id3
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="farmID",
    size= 225,
    required= True
)

result = db.create_integer_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="months_to_maturity",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="image_url",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="growth_conditions",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="packaging_weights", #Default weight (e.g., 2.5 kg, 500 g) assigned by Super Admin.
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="package_types",
    elements=["Small", "Medium", "Large"],
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="price_per_package",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="created_by",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id3,
    key="status",
    elements=["active", "inactive"],
    required= True
)