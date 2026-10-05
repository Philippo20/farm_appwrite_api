"""Idempotent additive migration. Existing plant types and batches remain unchanged."""
import os
import time
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException


def migrate():
    load_dotenv()
    db = Databases(Client().set_endpoint(os.environ['APPWRITE_ENDPOINT'])
        .set_project(os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY']))
    database = os.environ['APPWRITE_DB_ID']
    collections = [os.environ['APPWRITE_COLLECTION_ID3'], os.environ['APPWRITE_COLLECTION_ID5']]
    for collection in collections:
        try:
            db.create_string_attribute(database, collection, 'production_plan', 16384, False)
        except AppwriteException as error:
            if error.code != 409:
                raise
    # The existing maturity unit is an enum; add days without removing any values/defaults.
    attribute = db.get_attribute(database, collections[0], 'maturity_unit')
    if 'elements' in attribute and 'days' not in attribute['elements']:
        import requests
        from urllib.parse import quote
        path = f'/databases/{quote(database, safe="")}/collections/{quote(collections[0], safe="")}/attributes/enum/maturity_unit'
        response = requests.patch(db.client._endpoint + path,
            headers={**db.client._global_headers, 'content-type': 'application/json'},
            json={'elements': attribute['elements'] + ['days'], 'required': attribute['required'], 'default': attribute.get('default')}, timeout=30)
        response.raise_for_status()
    for _ in range(25):
        attributes = [db.get_attribute(database, collection, 'production_plan') for collection in collections]
        attributes.append(db.get_attribute(database, collections[0], 'maturity_unit'))
        if all(a['status'] == 'available' for a in attributes):
            if 'elements' in attributes[-1] and 'days' not in attributes[-1]['elements']:
                raise RuntimeError('Maturity unit does not accept days')
            print('Production plan schema ready; existing records preserved.')
            return
        if any(a['status'] in ('failed', 'stuck') for a in attributes):
            raise RuntimeError('Production plan schema failed to build')
        time.sleep(2)
    raise RuntimeError('Schema still building; rerun migration to verify')


if __name__ == '__main__':
    migrate()
