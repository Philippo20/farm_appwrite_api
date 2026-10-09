"""Create optional per-user typography storage; existing users keep defaults."""
import time
from appwrite.exception import AppwriteException
from db import db
from main import db_id, db_collection_id1


def setup():
    try:
        db.create_string_attribute(database_id=db_id, collection_id=db_collection_id1,
            key='typography_preferences', size=512, required=False)
    except AppwriteException as error:
        if error.code != 409:
            raise
    for _ in range(45):
        field = db.get_attribute(db_id, db_collection_id1, 'typography_preferences')
        if field.get('status') == 'available':
            if field.get('type') != 'string' or field.get('array') or field.get('size', 0) < 512:
                raise RuntimeError('Incompatible personal typography attribute.')
            print('Personal typography preferences ready. Existing users retain default sizes.')
            return
        if field.get('status') in {'failed', 'stuck'}:
            raise RuntimeError('Personal typography attribute failed.')
        time.sleep(1)
    raise RuntimeError('Personal typography attribute still processing; rerun migration.')


if __name__ == '__main__':
    setup()
