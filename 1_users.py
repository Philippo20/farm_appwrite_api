from main import client, db_id
from main import db_collection_id1
from appwrite.services.databases import Databases

db = Databases(client)

SUPERADMIN = "superadmin"
FARM_MANAGER = "farm_manager"
FARM_OWNER = "farm_owner"
CARETAKER = "caretaker"
TECHNICIAN = "technician"
FULFILLMENT = "fulfillment_manager"
PACKAGING = "packaging_supervisor"
QA = "quality_assurance_officer"
SALES_MANAGER = "sales_manager"
SALES_PERSON = "sales_person"
ACCOUNTANT = "accountant"

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
        elements=["superadmin", "farm_manager", "farm_owner", "caretaker", "technician", "fulfillment_manager", "packaging_supervisor", "quality_officer", "sales_manager", "sales_person", "accountant"],
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