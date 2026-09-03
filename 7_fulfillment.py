from main import client, db_id
from main import db_collection_id7
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="fulfillment_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="batch_number",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="farm_manager_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="farm_name",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="plant_type",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="total_heads",
    required= True,
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="total_weight",
    required= True,
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="harvest_received_images",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="packaging_supervisor_id",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="packaging_type",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="packaging_weight",
    required= True,
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="total_packaged_weight",
    required= True,
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="packaging_waste_type",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="packaging_waste_weight",
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="packaging_images",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="yield_loss_percentage",
    required= True,
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="received_date_time",
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="packaging_date_time",
    required= True
)

result = db.create_boolean_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="sent_to_sales",
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="sent_to_sales_date_time",
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="status",
    elements=["Received", "Packaging", "Packaged", "Sent to Sales", "Completed"],
    required= True
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_status",
    elements=["Pending Inspection", "Inspected", "Approved", "Rejected"],
    required=False,
    default="Pending Inspection"
)

result = db.create_float_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_score",
    required=False,
    default=0.0
)

result = db.create_enum_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_grade",
    elements=["Pending", "Grade A", "Grade B", "Grade C", "Rejected"],
    required=False,
    default="Pending"
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_checks",
    size=2000,
    required=False,
    default="{}"
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_notes",
    size=1000,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_inspector_id",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_inspector_name",
    size=225,
    required=False,
    default=""
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_inspected_at",
    required=False
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_decision_by_id",
    size=225,
    required=False,
    default=""
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_decision_by_name",
    size=225,
    required=False,
    default=""
)

result = db.create_datetime_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_decided_at",
    required=False
)

result = db.create_string_attribute(
    database_id=db_id,
    collection_id=db_collection_id7,
    key="quality_rejection_reason",
    size=1000,
    required=False,
    default=""
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="delivery_status",
    elements=["Pending Approval", "Pending Pickup", "Scheduled", "In Transit", "Delivered", "On Hold", "Cancelled", "Rejected"],
    required= False,
    default="Pending Approval"
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="driver_name",
    size= 225,
    required= False,
    default="Unassigned"
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="vehicle",
    size= 225,
    required= False,
    default="Pending"
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="destination",
    size= 225,
    required= False,
    default="Sales Hub"
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="address",
    size= 500,
    required= False,
    default=""
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="scheduled_date",
    required= False
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="eta",
    size= 225,
    required= False,
    default=""
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="temperature",
    size= 50,
    required= False,
    default="N/A"
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="priority",
    elements=["High", "Medium", "Low"],
    required= False,
    default="Medium"
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id7,
    key="delivery_note",
    size= 1000,
    required= False,
    default=""
)
