"""Add multiple caretaker assignments while preserving legacy farms."""
import time
from appwrite.exception import AppwriteException
from db import db
from main import db_id, db_collection_id2


def setup():
    try:
        db.create_string_attribute(database_id=db_id, collection_id=db_collection_id2,
                                   key='caretaker_ids', size=36, required=False, array=True)
    except AppwriteException as error:
        if error.code != 409:
            raise
    for _ in range(45):
        field = db.get_attribute(database_id=db_id, collection_id=db_collection_id2, key='caretaker_ids')
        if field.get('status') == 'available':
            if field.get('type') != 'string' or not field.get('array'):
                raise RuntimeError('Existing caretaker_ids attribute must be a string array.')
            print('Farm caretaker_ids attribute ready. Existing assignments are preserved.')
            return
        if field.get('status') in {'failed', 'stuck'}:
            raise RuntimeError('Farm caretaker_ids attribute could not be created.')
        time.sleep(1)
    raise RuntimeError('Farm caretaker_ids attribute still processing; rerun this migration.')


if __name__ == '__main__':
    setup()
