"""Private V1.7 history and independent linked equipment. Safe to rerun."""
import os
from urllib.parse import quote
import requests
from appwrite.exception import AppwriteException
from migrate_calibration_events import create_if_missing, wait_ready
from controller_activity import EQUIPMENT_OUTPUTS

def ensure_index(db, database, collection, name, attributes):
    try:
        db.get_index(database, collection, name)
    except AppwriteException as error:
        if error.code != 404: raise
        try:
            db.create_index(database, collection, name, 'key', attributes)
        except AppwriteException as error:
            if error.code != 409 and not (error.code == 400 and 'same attributes' in str(error).lower()): raise
            equivalent = [index for index in db.list_indexes(database, collection)['indexes']
                if index.get('type') == 'key' and index.get('attributes') == attributes]
            if not equivalent: raise RuntimeError('Required controller index is incompatible: ' + name) from error
            name = equivalent[0]['key']
    index = wait_ready(lambda: [db.get_index(database, collection, name)])[0]
    if index.get('type') != 'key' or index.get('attributes') != attributes:
        raise RuntimeError('Incompatible controller index: ' + name)

def migrate(db, database, devices, activity='controller_activity_events', bindings='controller_output_bindings'):
    attribute = db.get_attribute(database, devices, 'sensortype')
    missing = [kind for kind in EQUIPMENT_OUTPUTS if kind not in attribute['elements']]
    if missing:
        path = '/databases/{}/collections/{}/attributes/enum/sensortype'.format(quote(database, safe=''), quote(devices, safe=''))
        response = requests.patch(db.client._endpoint + path,
            headers={**db.client._global_headers, 'content-type': 'application/json'},
            json={'elements': [*attribute['elements'], *missing], 'required': attribute['required'], 'default': attribute.get('default')}, timeout=30)
        if not response.ok: raise RuntimeError('Unable to add equipment types.')
    for name in ['controller_id', 'controller_output']:
        create_if_missing(lambda: db.create_string_attribute(database, devices, name, 64, False))
    device_fields = wait_ready(lambda: [db.get_attribute(database, devices, name) for name in ['sensortype', 'controller_id', 'controller_output']])
    if any(kind not in device_fields[0]['elements'] for kind in EQUIPMENT_OUTPUTS):
        raise RuntimeError('Equipment types are not available yet.')
    for field in device_fields[1:]:
        if field.get('type') != 'string' or field.get('required') or field.get('array') or field.get('size', 0) < 64:
            raise RuntimeError('Incompatible equipment link attribute: ' + field['key'])
    ensure_index(db, database, devices, 'equipment_controller', ['controller_id'])
    collections = {
        activity: {'sensor_id': 64, 'event_id': 100, 'session_id': 64, 'event_type': 64, 'payload': 8192},
        bindings: {'controller_id': 64, 'output': 64, 'device_id': 64},
    }
    for collection, strings in collections.items():
        create_if_missing(lambda: db.create_collection(database, collection, collection.replace('_', ' ').title(), permissions=[], document_security=False))
        if db.get_collection(database, collection).get('$permissions'):
            raise RuntimeError('Controller collections must remain private.')
        for name, size in strings.items():
            create_if_missing(lambda: db.create_string_attribute(database, collection, name, size, True))
        if collection == activity:
            create_if_missing(lambda: db.create_datetime_attribute(database, collection, 'received_at', True))
            create_if_missing(lambda: db.create_integer_attribute(database, collection, 'generation', True, min=0, max=9007199254740991))
            create_if_missing(lambda: db.create_boolean_attribute(database, collection, 'notification_pending', True))
        names = [*strings, *(['received_at', 'generation', 'notification_pending'] if collection == activity else [])]
        fields = wait_ready(lambda: [db.get_attribute(database, collection, name) for name in names])
        for field in fields:
            name = field['key']
            expected = 'string' if name in strings else 'datetime' if name == 'received_at' else 'boolean' if name == 'notification_pending' else 'integer'
            if field.get('type') != expected or not field.get('required') or field.get('array') or (name in strings and field.get('size', 0) < strings[name]):
                raise RuntimeError('Incompatible controller schema: ' + name)
    indexes = {'current_boot': ['sensor_id', 'session_id', 'generation'], 'activity_history': ['sensor_id', 'received_at'], 'pending_notifications': ['notification_pending', 'received_at']}
    for name, attributes in indexes.items():
        ensure_index(db, database, activity, name, attributes)

if __name__ == '__main__':
    from dotenv import load_dotenv
    from appwrite.client import Client
    from appwrite.services.databases import Databases
    load_dotenv()
    db = Databases(Client().set_endpoint(os.environ['APPWRITE_ENDPOINT']).set_project(os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY']))
    migrate(db, os.environ['APPWRITE_DB_ID'], os.environ['APPWRITE_COLLECTION_ID11'],
        os.getenv('APPWRITE_CONTROLLER_ACTIVITY_COLLECTION', 'controller_activity_events'),
        os.getenv('APPWRITE_CONTROLLER_BINDINGS_COLLECTION', 'controller_output_bindings'))
    print('Controller activity and linked equipment schema ready.')
