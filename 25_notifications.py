from main import client, db_id, db_collection_id25
from appwrite.services.databases import Databases

db = Databases(client)

db.create_string_attribute(database_id=db_id, collection_id=db_collection_id25,
                           key="notification_id", size=225, required=True)
db.create_string_attribute(database_id=db_id, collection_id=db_collection_id25,
                           key="recipient_id", size=225, required=True)
db.create_string_attribute(database_id=db_id, collection_id=db_collection_id25,
                           key="recipient_name", size=225, required=False, default="")
db.create_string_attribute(database_id=db_id, collection_id=db_collection_id25,
                           key="title", size=225, required=True)
db.create_string_attribute(database_id=db_id, collection_id=db_collection_id25,
                           key="message", size=2000, required=True)
db.create_string_attribute(database_id=db_id, collection_id=db_collection_id25,
                           key="type", size=80, required=True)
db.create_string_attribute(database_id=db_id, collection_id=db_collection_id25,
                           key="related_task_id", size=225, required=False, default="")
db.create_enum_attribute(database_id=db_id, collection_id=db_collection_id25,
                         key="priority", elements=["low", "normal", "high", "urgent"],
                         required=True)
db.create_boolean_attribute(database_id=db_id, collection_id=db_collection_id25,
                            key="is_read", required=True)
db.create_datetime_attribute(database_id=db_id, collection_id=db_collection_id25,
                             key="created_at", required=True)
