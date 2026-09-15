"""Add water_temperature to existing sensor/alert enums. Run once before deploying water_temperature support."""
import os


def add_water_temperature(db, database_id, collection_id, key):
    attribute = db.get_attribute(database_id, collection_id, key)
    elements = list(attribute['elements'])
    if 'water_temperature' in elements:
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
        json={'elements': [*elements, 'water_temperature'],
              'required': attribute['required'], 'default': attribute.get('default')},
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(response.json().get('message', 'Database enum update failed'))
    verified = db.get_attribute(database_id, collection_id, key)
    if 'water_temperature' not in verified['elements']:
        raise RuntimeError('Water temperature enum verification failed')
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
        changed = add_water_temperature(db, os.environ['APPWRITE_DB_ID'], os.environ[variable], key)
        print(key + (': water_temperature added' if changed else ': water_temperature already available'))


if __name__ == '__main__':
    main()
