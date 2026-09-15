"""Add light_switch to existing sensor/alert enums. Run once before deploying light_switch support."""
import os


def add_light_switch(db, database_id, collection_id, key):
    attribute = db.get_attribute(database_id, collection_id, key)
    elements = list(attribute['elements'])
    if 'light_switch' in elements:
        return False
    # SDK 11 omits None parameters, but this server requires explicit null.
    # Preserve the existing default rather than inventing a new one.
    import requests
    from urllib.parse import quote
    path = '/databases/{}/collections/{}/attributes/enum/{}'.format(
        quote(database_id, safe=''), quote(collection_id, safe=''), quote(key, safe=''))
    response = requests.patch(
        db.client._endpoint + path,
        headers={**db.client._global_headers, 'content-type': 'application/json'},
        json={'elements': [*elements, 'light_switch'],
              'required': attribute['required'], 'default': attribute.get('default')},
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(response.json().get('message', 'Database enum update failed'))
    verified = db.get_attribute(database_id, collection_id, key)
    if 'light_switch' not in verified['elements']:
        raise RuntimeError('Light switch enum verification failed')
    return True


def main():
    from dotenv import load_dotenv
    from appwrite.client import Client
    from appwrite.services.databases import Databases
    load_dotenv()
    client = (Client().set_endpoint(os.environ['APPWRITE_ENDPOINT'])
              .set_project(os.environ['APPWRITE_PROJECT_ID'])
              .set_key(os.environ['APPWRITE_API_KEY']))
    db = Databases(client)
    for variable, key in [('APPWRITE_COLLECTION_ID11', 'sensortype'),
                          ('APPWRITE_COLLECTION_ID12', 'sensorType')]:
        changed = add_light_switch(db, os.environ['APPWRITE_DB_ID'], os.environ[variable], key)
        print(key + (': light_switch added' if changed else ': light_switch already available'))


def create_control_collection():
    import time
    from dotenv import load_dotenv
    from appwrite.client import Client
    from appwrite.services.databases import Databases
    from appwrite.exception import AppwriteException
    load_dotenv()
    db = Databases(Client().set_endpoint(os.environ['APPWRITE_ENDPOINT']).set_project(os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY']))
    database = os.environ['APPWRITE_DB_ID']
    collection = os.getenv('APPWRITE_SWITCH_CONTROL_COLLECTION', 'switch_control')
    try:
        db.create_collection(database, collection, 'Light switch control', permissions=[], document_security=False)
    except AppwriteException as error:
        if error.code != 409: raise
    for name, size in [('sensor_id', 64), ('kind', 20), ('payload', 8192)]:
        try:
            db.create_string_attribute(database, collection, name, size, True)
        except AppwriteException as error:
            if error.code != 409: raise
    for attempt in range(20):
        if all(db.get_attribute(database, collection, name)['status'] == 'available' for name in ['sensor_id', 'kind', 'payload']): break
        time.sleep(2)
    else: raise RuntimeError('Attributes are still building. Rerun the migration later.')
    try:
        db.create_index(database, collection, 'sensor_kind', 'key', ['sensor_id', 'kind'])
    except AppwriteException as error:
        if error.code != 409: raise
    print('Private switch control collection is ready; indexes may finish asynchronously.')

if __name__ == '__main__':
    main()
    create_control_collection()
