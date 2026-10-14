"""Idempotent command device schema migration; preserves existing sensor types."""
import os
import time
from urllib.parse import quote
import requests
from appwrite.exception import AppwriteException
from migrate_light_switches import create_control_collection

def migrate(db, database, collection):
    attribute = db.get_attribute(database, collection, 'sensortype')
    if 'command_device' not in attribute['elements']:
        path = '/databases/{}/collections/{}/attributes/enum/sensortype'.format(
            quote(database, safe=''), quote(collection, safe=''))
        response = requests.patch(db.client._endpoint + path,
            headers={**db.client._global_headers, 'content-type': 'application/json'},
            json={'elements': [*attribute['elements'], 'command_device'],
                  'required': attribute['required'], 'default': attribute.get('default')}, timeout=30)
        if not response.ok:
            raise RuntimeError('Unable to add command_device to the sensor type enum.')
    try:
        db.create_string_attribute(database, collection, 'command_config', 8192, False)
    except AppwriteException as error:
        if error.code != 409:
            raise
    for attempt in range(30):
        fields = [db.get_attribute(database, collection, name) for name in ['sensortype', 'command_config']]
        if all(field['status'] == 'available' for field in fields):
            if ('command_device' not in fields[0]['elements'] or fields[1].get('size', 0) < 8192
                    or fields[1].get('required') or fields[1].get('type') != 'string' or fields[1].get('array')):
                raise RuntimeError('Command device attributes do not match the required schema.')
            return
        time.sleep(2)
    raise RuntimeError('Attributes are still building. Rerun the migration before deployment.')

def ensure_controls(db, database, collection):
    try:
        create_control_collection()
    except AppwriteException as error:
        if error.code != 400 or 'index' not in str(error).lower() or 'same attributes' not in str(error).lower():
            raise
        # An equivalent index can have a different name on an existing project.
    for name, size in [('sensor_id', 64), ('kind', 20), ('payload', 8192)]:
        field = db.get_attribute(database, collection, name)
        if (field.get('status') != 'available' or field.get('type') != 'string'
                or field.get('size', 0) < size or not field.get('required') or field.get('array')):
            raise RuntimeError('Private control storage has an incompatible attribute: ' + name)
    for attempt in range(30):
        indexes = db.list_indexes(database, collection)['indexes']
        compatible = [index for index in indexes if index.get('type') == 'key'
                      and set(index.get('attributes', [])) == {'sensor_id', 'kind'}]
        if any(index.get('status') == 'available' for index in compatible):
            return
        if not compatible or any(index.get('status') == 'failed' for index in compatible):
            raise RuntimeError('A sensor_id/kind control index is required.')
        time.sleep(2)
    raise RuntimeError('The control index is still building. Rerun the migration before deployment.')

if __name__ == '__main__':
    from dotenv import load_dotenv
    from appwrite.client import Client
    from appwrite.services.databases import Databases
    load_dotenv()
    client = Client().set_endpoint(os.environ['APPWRITE_ENDPOINT']).set_project(os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY'])
    db = Databases(client)
    migrate(db, os.environ['APPWRITE_DB_ID'], os.environ['APPWRITE_COLLECTION_ID11'])
    ensure_controls(db, os.environ['APPWRITE_DB_ID'], os.getenv('APPWRITE_SWITCH_CONTROL_COLLECTION', 'switch_control'))
    print('Command device type, configuration and private control storage are ready.')
