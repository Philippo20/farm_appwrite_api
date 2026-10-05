"""Add the first-login password flag; existing accounts remain unaffected."""
import os
import time
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException


if __name__ == '__main__':
    load_dotenv()
    client = Client().set_endpoint(os.environ['APPWRITE_ENDPOINT']).set_project(
        os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY'])
    db = Databases(client)
    database, collection = os.environ['APPWRITE_DB_ID'], os.environ['APPWRITE_COLLECTION_ID1']
    field = 'must_change_password'
    try:
        db.create_boolean_attribute(database, collection, field, required=False, default=False)
    except AppwriteException as error:
        if error.code != 409:
            raise
    for attempt in range(20):
        attribute = db.get_attribute(database, collection, field)
        if attribute['status'] == 'available':
            if attribute.get('type') != 'boolean' or attribute.get('required') or attribute.get('default') is not False:
                raise RuntimeError('Unexpected existing first-password attribute schema')
            print('must_change_password: available (optional boolean, default false)')
            break
        if attribute['status'] in ('failed', 'stuck'):
            raise RuntimeError('First-password attribute failed to build')
        time.sleep(2)
    else:
        raise RuntimeError('Attribute still building; rerun to verify')
