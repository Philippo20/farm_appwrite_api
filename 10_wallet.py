from main import client, db_id
from main import db_collection_id10
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="user_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="user_name",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="role",
    elements=["superadmin", "farm_manager", "farm_owner", "caretaker", "fulfillment_manager", "packaging_supervisor", "quality_officer", "sales_manager", "sales_person", "accountant"],
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="balance",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="currency",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="total_credits",
    required= True,
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="total_debits",
    required= True,
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="transaction_image",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="transaction_id",
    size= 225,
    required= False
) 

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="status",
    elements=["Active", "Frozen", "Closed"],
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="created_at",
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="updated_at",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="created_by",
    size= 225,
    required= True
)