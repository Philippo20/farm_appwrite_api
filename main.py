from fastapi import FastAPI
from appwrite.client import Client
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("APPWRITE_API_KEY")
project_id = os.getenv("APPWRITE_PROJECT_ID")
appwrite_endpoint = os.getenv("APPWRITE_ENDPOINT")
db_id = os.getenv("APPWRITE_DB_ID")
bucket_id= os.getenv("APPWRITE_BUCKET_ID")  
db_collection_id1 = os.getenv("APPWRITE_COLLECTION_ID1")
db_collection_id2 = os.getenv("APPWRITE_COLLECTION_ID2")
db_collection_id3 = os.getenv("APPWRITE_COLLECTION_ID3")
db_collection_id4 = os.getenv("APPWRITE_COLLECTION_ID4")
db_collection_id5 = os.getenv("APPWRITE_COLLECTION_ID5")
db_collection_id6 = os.getenv("APPWRITE_COLLECTION_ID6")
db_collection_id7 = os.getenv("APPWRITE_COLLECTION_ID7")
db_collection_id8 = os.getenv("APPWRITE_COLLECTION_ID8")
db_collection_id9 = os.getenv("APPWRITE_COLLECTION_ID9")
db_collection_id10 = os.getenv("APPWRITE_COLLECTION_ID10")
db_collection_id11 = os.getenv("APPWRITE_COLLECTION_ID11")
db_collection_id12 = os.getenv("APPWRITE_COLLECTION_ID12")
db_collection_id13 = os.getenv("APPWRITE_COLLECTION_ID13")
db_collection_id14 = os.getenv("APPWRITE_COLLECTION_ID14")
db_collection_id15 = os.getenv("APPWRITE_COLLECTION_ID15")
db_collection_id16 = os.getenv("APPWRITE_COLLECTION_ID16")
db_collection_id17 = os.getenv("APPWRITE_COLLECTION_ID17")
db_collection_id18 = os.getenv("APPWRITE_COLLECTION_ID18")
db_collection_id19 = os.getenv("APPWRITE_COLLECTION_ID19")
db_collection_id20 = os.getenv("APPWRITE_COLLECTION_ID20")
db_collection_id21 = os.getenv("APPWRITE_COLLECTION_ID21")
db_collection_id22 = os.getenv("APPWRITE_COLLECTION_ID22", "fund_requests")
db_collection_id23 = os.getenv("APPWRITE_COLLECTION_ID23", "farm_tasks")
db_collection_id24 = os.getenv("APPWRITE_COLLECTION_ID24", "farm_records")
db_collection_id25 = os.getenv("APPWRITE_COLLECTION_ID25", "notifications")
db_collection_id26 = os.getenv("APPWRITE_COLLECTION_ID26", "input_confirmations")
db_collection_id27 = os.getenv("APPWRITE_COLLECTION_ID27", "caretaker_settings")

client = Client()

client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
client.set_key(os.getenv("APPWRITE_API_KEY"))

client.set_self_signed(
    os.getenv("APPWRITE_SELF_SIGNED", "false").strip().lower() == "true"
)
