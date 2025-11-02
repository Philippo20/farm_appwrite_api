from main import client, db_id
from main import db_collection_id4
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="item_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="item_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="item_type",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="unit",
    size= 225,
    required= True
)


result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="quantity_available",
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="reorder_level",
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="unit_price",
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="total_value",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="supplier_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="batch_number",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="farm_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="added_by",
    size= 225,
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="date_added",
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="status",
    elements=["Available", "Low Stock", "Out of Stock", "Expired"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id4,
    key="notes",
    size= 225,
    required= False
)