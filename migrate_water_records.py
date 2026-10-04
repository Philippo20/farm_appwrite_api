"""Add optional water purchase and AC water fields without changing old records."""
import os
import time
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException

if __name__ == '__main__':
    load_dotenv()
    db = Databases(Client().set_endpoint(os.environ['APPWRITE_ENDPOINT']).set_project(os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY']))
    database = os.environ['APPWRITE_DB_ID']
    collection = os.environ['APPWRITE_COLLECTION_ID24']
    fields = ['water_bought_litres', 'water_bought_amount', 'ac_water_litres', 'water_temperature']
    for field in fields:
        try:
            db.create_float_attribute(database, collection, field, False, **({} if field == 'water_temperature' else {'min': 0}))
        except AppwriteException as error:
            if error.code != 409: raise
    for attempt in range(20):
        attributes = [db.get_attribute(database, collection, field) for field in fields]
        if all(a['status'] == 'available' for a in attributes):
            for a in attributes:
                if a.get('type') != 'double' or a.get('required'):
                    raise RuntimeError('Unexpected existing schema for ' + a['key'])
                print(a['key'] + ': available (optional number)')
            break
        time.sleep(2)
    else:
        raise RuntimeError('Attributes still building; rerun to verify.')
