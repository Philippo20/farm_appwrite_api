"""Add optional per-task device plans and private, append-only completion records."""
import os
import time
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException


def ensure(action):
    try: return action()
    except AppwriteException as error:
        if error.code != 409: raise


if __name__ == '__main__':
    load_dotenv()
    db = Databases(Client().set_endpoint(os.environ['APPWRITE_ENDPOINT']).set_project(
        os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY']))
    database, devices = os.environ['APPWRITE_DB_ID'], os.environ['APPWRITE_COLLECTION_ID11']
    history = os.getenv('APPWRITE_DEVICE_MAINTENANCE_HISTORY', 'device_maintenance_history')
    ensure(lambda: db.create_string_attribute(database, devices, 'maintenance_plan', 16384, False))
    kind = db.get_attribute(database, devices, 'sensortype')
    elements = list(kind['elements'])
    if 'air_conditioner' not in elements:
        import requests
        from urllib.parse import quote
        path = f'/databases/{quote(database, safe="")}/collections/{quote(devices, safe="")}/attributes/enum/sensortype'
        response = requests.patch(db.client._endpoint + path,
            headers={**db.client._global_headers, 'content-type': 'application/json'},
            json={'elements': elements + ['air_conditioner'], 'required': kind['required'], 'default': kind.get('default')}, timeout=30)
        if not response.ok: raise RuntimeError('Air conditioner enum migration failed: ' + str(response.status_code))
    ensure(lambda: db.create_collection(database, history, 'Device maintenance history', permissions=[], document_security=False))
    for name, size in [('device_id', 64), ('farm_id', 64), ('payload', 16384)]:
        ensure(lambda: db.create_string_attribute(database, history, name, size, True))
    for attempt in range(25):
        attributes = [db.get_attribute(database, devices, 'maintenance_plan'),
                      db.get_attribute(database, devices, 'sensortype'),
                      *[db.get_attribute(database, history, key) for key in ('device_id', 'farm_id', 'payload')]]
        if all(attribute['status'] == 'available' for attribute in attributes): break
        if any(attribute['status'] in ('failed', 'stuck') for attribute in attributes):
            raise RuntimeError('Maintenance schema failed to build')
        time.sleep(2)
    else: raise RuntimeError('Maintenance schema still building; rerun to verify')
    ensure(lambda: db.create_index(database, history, 'device_history', 'key', ['device_id']))
    for attempt in range(25):
        if db.get_index(database, history, 'device_history')['status'] == 'available': break
        time.sleep(2)
    else: raise RuntimeError('History index still building; rerun to verify')
    print('Device maintenance plans, air conditioner type and private history are ready. Existing records preserved.')
