from main import client, db_id
from main import db_collection_id6
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="audit_id",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="action_type",
    elements=["Create", "Update", "Delete", "Login", "Approval", "Suspension"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="collection_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="performed_by_id",
    size= 225,
    required= True
)


result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="performed_by_role",
    elements=["superadmin", "admin", "farm_manager", "farm_owner", "caretaker", "technician", "fulfillment_manager", "packaging_supervisor", "quality_officer", "sales_manager", "sales_person", "accountant"],
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="timestamp",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="action_details",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="ip_address",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="status",
    elements=["Success", "Failed", "Pending"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="previous_data",
    size= 225,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id6,
    key="new_data",
    size= 225,
    required= False
)
