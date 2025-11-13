from main import client, db_id
from main import db_collection_id11
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes
result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="farmID",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="farm_name",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="sensortype",
    elements=["temperature", "humidity", "Carbon Dioxide","light", "pH Level", "EC Level", "Water level","electricity_current", "electricity_voltage", "electricity_wattage"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="model_number",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="serial_number",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="location",
    size= 225,
    required= True
)

result = db.create_float_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="value", #recent value recorded
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="status",
    elements=["Active", "Inactive", "Faulty", "Maintenance"],
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="unit", #°C, %, ppm, lux, pH, mS/cm, A, V, W
    size=225,
    required= True
)

result = db.create_boolean_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="alerts_enabled", #Whether automatic alert notifications are turned on.
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="maintenance_frequency", #weekly, monthly, quarterly
    size=225,
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="timestamp",#last reading time
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id11,
    key="last_maintenance_date",#Last date sensor was serviced.
    required= True
)