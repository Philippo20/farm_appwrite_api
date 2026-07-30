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

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="created_by",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="transaction_type",
    elements=["Balance", "Credit", "Debit", "Withdrawal", "Payout Account"],
    required= False
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="withdrawal_status",
    elements=["Pending", "Approved", "Rejected", "Paid"],
    required= False
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="amount",
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="bank_account",
    size= 225,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="note",
    size= 1000,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="farm_id",
    size= 225,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="farm_name",
    size= 225,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="requested_at",
    size= 80,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="processed_at",
    size= 80,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="decision_notes",
    size= 1000,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="account_name",
    size= 225,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="account_number",
    size= 80,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="bank_name",
    size= 225,
    required= False
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id10,
    key="payout_method",
    elements=["Bank", "Mobile Money"],
    required= False
)
