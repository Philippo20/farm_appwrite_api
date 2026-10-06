"""Idempotent, server-only device registry. Run before enabling FCM."""
import time
from appwrite.exception import AppwriteException
from db import db
from main import db_id
from push_notifications import DEVICES

def setup():
    try:
        db.create_collection(database_id=db_id, collection_id=DEVICES, name='Push devices', permissions=[], document_security=False)
    except AppwriteException as error:
        if error.code != 409: raise
    fields = [('token', 4096), ('recipient_id', 36), ('platform', 20), ('updated_at', 80)]
    for key, size in fields:
        try:
            db.create_string_attribute(database_id=db_id, collection_id=DEVICES, key=key, size=size, required=True)
        except AppwriteException as error:
            if error.code != 409: raise
    for _ in range(45):
        attributes = db.list_attributes(database_id=db_id, collection_id=DEVICES)['attributes']
        if all(any(a['key'] == key and a['status'] == 'available' for a in attributes) for key, _ in fields): break
        time.sleep(1)
    else: raise RuntimeError('Push attributes are still being created. Run setup again.')
    try:
        db.create_index(database_id=db_id, collection_id=DEVICES, key='recipient_id', type='key', attributes=['recipient_id'])
    except AppwriteException as error:
        if error.code != 409: raise
    print('Push device registry ready.')

if __name__ == '__main__': setup()
