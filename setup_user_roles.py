"""Add optional assigned roles. Existing users retain their primary role without backfill."""
import time
from appwrite.exception import AppwriteException
from db import db
from main import db_id, db_collection_id1


def setup():
    try:
        db.create_string_attribute(database_id=db_id, collection_id=db_collection_id1,
                                   key='roles', size=40, required=False, array=True)
    except AppwriteException as error:
        if error.code != 409:
            raise
    for _ in range(45):
        field = db.get_attribute(database_id=db_id, collection_id=db_collection_id1, key='roles')
        if field.get('status') == 'available':
            if field.get('type') != 'string' or not field.get('array'):
                raise RuntimeError('Existing roles attribute must be a string array.')
            print('User roles attribute ready. Legacy accounts keep their primary role.')
            return
        if field.get('status') in {'failed', 'stuck'}:
            raise RuntimeError('User roles attribute could not be created.')
        time.sleep(1)
    raise RuntimeError('User roles attribute still processing; rerun this migration.')


if __name__ == '__main__':
    setup()
