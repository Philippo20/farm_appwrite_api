"""Create private indexed calibration history. Safe to rerun before deployment."""
import os
import time
from appwrite.exception import AppwriteException

STRINGS = {'sensor_id': 64, 'calibration_id': 36, 'target': 20, 'rack': 1, 'payload': 8192}
INDEXES = {
    'device_timeline': ['sensor_id', 'selection_at', 'uptime_ms', 'phase'],
    'calibration_timeline': ['sensor_id', 'calibration_id', 'selection_at', 'uptime_ms', 'phase'],
    'saved_target_timeline': ['sensor_id', 'saved', 'target', 'rack', 'selection_at', 'uptime_ms', 'phase'],
}

def create_if_missing(action):
    try:
        action()
    except AppwriteException as error:
        if error.code != 409:
            raise

def wait_ready(load):
    for _ in range(30):
        fields = load()
        if all(f['status'] == 'available' for f in fields):
            return fields
        if any(f['status'] == 'failed' for f in fields):
            raise RuntimeError('Calibration schema creation failed.')
        time.sleep(2)
    raise RuntimeError('Calibration schema is still building; rerun this migration.')

def migrate(db, database, collection='calibration_events'):
    create_if_missing(lambda: db.create_collection(database, collection,
        'Device calibration events', permissions=[], document_security=False))
    if db.get_collection(database, collection).get('$permissions'):
        raise RuntimeError('Calibration events collection must be private.')
    for name, size in STRINGS.items():
        create_if_missing(lambda: db.create_string_attribute(database, collection, name, size, True))
    for name in ['selection_at', 'received_at']:
        create_if_missing(lambda: db.create_datetime_attribute(database, collection, name, True))
    for name, maximum in [('uptime_ms', 9007199254740991), ('phase', 8)]:
        create_if_missing(lambda: db.create_integer_attribute(database, collection, name, True, min=0, max=maximum))
    create_if_missing(lambda: db.create_boolean_attribute(database, collection, 'saved', True))
    names = [*STRINGS, 'selection_at', 'received_at', 'uptime_ms', 'phase', 'saved']
    fields = wait_ready(lambda: [db.get_attribute(database, collection, name) for name in names])
    for field in fields:
        name = field['key']
        expected = 'string' if name in STRINGS else 'datetime' if name.endswith('_at') else 'boolean' if name == 'saved' else 'integer'
        if field.get('type') != expected or not field.get('required') or field.get('array'):
            raise RuntimeError('Incompatible calibration attribute: ' + name)
        if name in STRINGS and field.get('size', 0) < STRINGS[name]:
            raise RuntimeError('Calibration attribute is too small: ' + name)
    for name, attributes in INDEXES.items():
        create_if_missing(lambda: db.create_index(database, collection, name, 'key', attributes))
    indexes = wait_ready(lambda: [db.get_index(database, collection, name) for name in INDEXES])
    if any(index.get('type') != 'key' or index.get('attributes') != INDEXES[index['key']] for index in indexes):
        raise RuntimeError('Incompatible calibration history indexes.')

if __name__ == '__main__':
    from dotenv import load_dotenv
    from appwrite.client import Client
    from appwrite.services.databases import Databases
    load_dotenv()
    db = Databases(Client().set_endpoint(os.environ['APPWRITE_ENDPOINT'])
        .set_project(os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY']))
    migrate(db, os.environ['APPWRITE_DB_ID'], os.getenv('APPWRITE_CALIBRATION_EVENTS_COLLECTION', 'calibration_events'))
    print('Private calibration event storage and indexes are ready.')
