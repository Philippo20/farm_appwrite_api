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
    key="off_taker_id",
    size= 225,
    required= False
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="fulfillment_id",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="crop_variety",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="package_type",
    size=225,
    required=False,
    default=""
)

result = db.create_integer_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="package_count",
    required=False,
    min=0,
    default=0
)

result = db.create_float_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="unit_weight_kg",
    required=False,
    min=0,
    default=0
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="pricing_id",
    size=225,
    required=False,
    default=""
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="price_tier",
    elements=["Regular", "Bulk"],
    required=False,
    default="Regular"
)

result = db.create_float_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="unit_price",
    required=False,
    min=0,
    default=0
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="invoice_number",
    size=80,
    required=False,
    default=""
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="invoice_generated_at",
    required=False
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="sales_person_id",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="sales_person_name",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="delivery_agent_id",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="delivery_agent_name",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="delivery_vehicle",
    size=120,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="delivery_type",
    size=40,
    required=False,
    default="internal"
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="delivery_provider",
    size=120,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="delivery_plate_number",
    size=80,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="delivery_address",
    size=500,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="delivery_notes",
    size=1000,
    required=False,
    default=""
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

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="scheduled_for",
    required=False
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id8,
    key="completed_at",
    required=False
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
