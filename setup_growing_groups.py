"""Add optional growing-group fields without rewriting existing batches/records."""
import time
from appwrite.exception import AppwriteException
from db import db
from main import db_id, db_collection_id5, db_collection_id24


def setup():
    fields = [(db_collection_id5, 'growing_group_id', 36, False),
              (db_collection_id5, 'growing_group_name', 100, False),
              (db_collection_id24, 'growing_group_id', 36, False),
              (db_collection_id24, 'growing_group_name', 100, False),
              (db_collection_id24, 'linked_batch_ids', 36, True),
              (db_collection_id24, 'batch_entries', 60000, False)]
    for collection, key, size, array in fields:
        try:
            db.create_string_attribute(db_id, collection, key, size, False, array=array)
        except AppwriteException as error:
            if error.code != 409:
                raise
        for _ in range(45):
            attribute = db.get_attribute(db_id, collection, key)
            if attribute.get('status') == 'available':
                if attribute.get('type') != 'string' or bool(attribute.get('array')) != array or attribute.get('size', 0) < size:
                    raise RuntimeError(f'Incompatible existing attribute: {key}')
                break
            if attribute.get('status') in {'failed', 'stuck'}:
                raise RuntimeError(f'Could not create {key}')
            time.sleep(1)
        else:
            raise RuntimeError(f'{key} still processing; rerun migration.')
        print(f'{key} ready')
    # Array membership queries work without an index on the deployed Appwrite version.
    # It rejects explicit indexes on array attributes.
    for collection, key in [(db_collection_id5, 'growing_group_id')]:
        try:
            existing = db.get_index(db_id, collection, key)
            if existing.get('attributes') != [key]:
                raise RuntimeError(f'Incompatible existing index: {key}')
        except AppwriteException as error:
            if error.code != 404:
                raise
            db.create_index(db_id, collection, key, 'key', [key])
        for _ in range(45):
            index = db.get_index(db_id, collection, key)
            if index.get('status') == 'available':
                break
            if index.get('status') in {'failed', 'stuck'}:
                raise RuntimeError(f'Could not create {key} index')
            time.sleep(1)
        else:
            raise RuntimeError(f'{key} index still processing; rerun migration.')
        print(f'{key} index ready')


if __name__ == '__main__':
    setup()
