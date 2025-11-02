from main import client, db_id
from main import db_collection_id1
from appwrite.services.databases import Databases

db = Databases(client)

ROLE_SUPERADMIN = "superadmin"
ROLE_FARM_MANAGER = "farm_manager"
ROLE_FARM_OWNER = "farm_owner"
ROLE_CARETAKER = "caretaker"
ROLE_FULFILLMENT = "fulfillment_manager"
ROLE_PACKAGING = "packaging_supervisor"
ROLE_QA = "quality_officer"
ROLE_SALES_MANAGER = "sales_manager"
ROLE_SALES_PERSON = "sales_person"
ROLE_ACCOUNTANT = "accountant"

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id1,
    key="name",
    size=225,
    required= True
)


result = db.create_email_attribute(
    database_id= db_id,
    collection_id= db_collection_id1,
    key="email",
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id1,
    key="password",
    size=225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id1,
    key="role",
        elements=["superadmin", "farm_manager", "farm_owner", "caretaker", "fulfillment_manager", "packaging_supervisor", "quality_officer", "sales_manager", "sales_person", "accountant"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id1,
    key="address",
    size=225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id1,
    key="phone",
    size=225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id1,
    key="department",
    size=225,
    required= True
)