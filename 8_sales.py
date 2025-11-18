from main import client, db_id
from main import db_collection_id8
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="batch_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="batch_number",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="buyer_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="buyer_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="delivered_by",
    size= 225,
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="delivered_at",
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="quantity_delivered",
    required= True,
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="total_amount",
    required= True,
)

result = db.create_boolean_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="paid",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="payment_mode",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="receipt_image",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="receipt_number",
    size= 225,
    required= False
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="payment_date",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="created_by",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id8,
    key="status",
    elements=["Pending", "Delivered", "Cancelled"],
    required= True
)