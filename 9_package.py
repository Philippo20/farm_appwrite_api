from main import client, db_id
from main import db_collection_id9
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="package_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="package_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="plant_type_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="plant_type_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="material_used",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="weight_capacity",
    required= True,
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="unit",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="quantity_available",
    required= True,
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="cost_per_unit",
    required= True,
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="created_by",
    size= 225,
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="created_at",
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="updated_at",
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id9,
    key="status",
    elements=["Active", "Damaged", "Out_of_stock", "Archived"],
    required= True
)