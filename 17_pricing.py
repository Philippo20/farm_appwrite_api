from main import client, db_id
from main import db_collection_id17
from appwrite.services.databases import Databases

db = Databases(client)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="farm_id",
    size= 225,
    required= False,
    default="all"
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="farm_name",
    size= 225,
    required= False,
    default="Hub Pricing"
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="plant_type",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="crop_variety",
    size= 225,
    required= False,
    default=""
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="packaging",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="unit",
    size= 50,
    required= False,
    default="kg"
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="pricing_type",
    elements=["hub_purchase", "hub_sale"],
    required= False,
    default="hub_purchase"
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="regular_price", #recent value recorded
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="bulk_price", #recent value recorded
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id17,
    key="status",
    elements=["Active", "Review", "Inactive"],
    required= True
)
