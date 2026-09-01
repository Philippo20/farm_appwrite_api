from main import client, db_id
from main import db_collection_id5
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="batch_id", 
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="batch_no", #System-generated unique code (e.g., FA-20251001-20251101
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="farmID",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="farm_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="plant_type_ID", #plant type grown in this batch.
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="plant_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="plant_variety",
    size= 225,
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="farm_manager_id", #ID of the assigned farm manager
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="farm_manager_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="caretaker_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="caretaker_name",
    size= 225,
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="start_date", #The planting/nursery start date
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="end_date", #Expected harvest date
    required= False
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="actual_harvest_date", #Actual harvest completion date
    required= False
)

result = db.create_integer_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="total_seeds_nursed", #Number of seeds started for this batch
    required= True,
)

result = db.create_integer_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="total_transplanted", #Total number of plants or heads harvested
    required= True,
)

result = db.create_integer_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="total_harvested", #Total number of plants or heads harvested
    required= True,
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="total_weight_kg", #Total number of plants or heads harvested
    required= True,
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="harvest_images", #Proof images of harvested plants
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="production_status",
    elements=["Planted", "Growing", "Harvested", "Delivered", "Completed"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="technical_issues", #issue, status, technician_id
    size=225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="inputs_supplied", #Records of seeds, nutrients, and water supplied
    size=225,
    required= True
)

result = db.create_boolean_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="funds_requested",
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="financial_status",
    elements=["Pending", "Partially Paid", "Cleared"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="fund_request_id", #ID reference to accountant’s approval record
    size=225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="delivery_status",
    elements=["Pending", "In Transit", "Delivered"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="delivery_details", #delivered_by, delivery_date, total_weight, proof_images
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="created_by",
    size= 225,
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="created_at",#When the plant type was added.
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id5,
    key="updated_at",#Last updated timestamp
    required= True
)
