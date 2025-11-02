from main import client, db_id
from main import db_collection_id12
from appwrite.services.databases import Databases

db = Databases(client)

# define attributes

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id12,
    key="farmID",
    size= 225,
    required= True
)

result = db.create_string_attribute(
    database_id= db_id,
    collection_id= db_collection_id12,
    key="message",
    size= 225,
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id12,
    key="sensorType",
    elements=["temperature", "humidity", "Carbon Dioxide", "light", "pH", "ec", "electricity_current", "electricity_voltage", "electricity_wattage"],
    required= True
)

result = db.create_enum_attribute(
    database_id= db_id,
    collection_id= db_collection_id12,
    key="severity",
    elements=["low", "medium", "high"],
    required= True
)

result = db.create_datetime_attribute(
    database_id= db_id,
    collection_id= db_collection_id12,
    key="timestamp",
    required= True
)

result = db.create_boolean_attribute(
    database_id= db_id,
    collection_id= db_collection_id12,
    key="resolved",
    required= False
)