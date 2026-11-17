"""Add nullable historical quantities, provenance, measurements, and batch numbering.

Existing values are preserved. Run before deploying the UI/API changes.
"""
import os
import time
import requests
from urllib.parse import quote
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException
from batch_numbers import COLLECTION


def connection():
    load_dotenv()
    return Databases(Client().set_endpoint(os.environ['APPWRITE_ENDPOINT']).set_project(
        os.environ['APPWRITE_PROJECT_ID']).set_key(os.environ['APPWRITE_API_KEY'])), os.environ['APPWRITE_DB_ID']


def ensure(db, database, collection, key, kind, size=None):
    try:
        if kind == 'string': db.create_string_attribute(database, collection, key, size, False)
        elif kind == 'boolean': db.create_boolean_attribute(database, collection, key, False)
        elif kind == 'integer': db.create_integer_attribute(database, collection, key, False, min=0)
        else: db.create_float_attribute(database, collection, key, False, min=0)
    except AppwriteException as error:
        if error.code != 409: raise
    for _ in range(45):
        field = db.get_attribute(database, collection, key)
        if field.get('status') == 'available':
            expected = 'double' if kind == 'float' else kind
            if field.get('type') != expected or field.get('required') or (size and field.get('size', 0) < size):
                raise RuntimeError('Incompatible attribute: ' + key)
            return
        if field.get('status') in ('failed', 'stuck'): raise RuntimeError('Failed attribute: ' + key)
        time.sleep(1)
    raise RuntimeError('Attribute not ready: ' + key)


def migrate():
    db, database = connection()
    batches, crops, records = [os.environ[f'APPWRITE_COLLECTION_ID{n}'] for n in (5,16,24)]
    try: db.create_collection(database, COLLECTION, 'Batch number reservations', permissions=[], document_security=False)
    except AppwriteException as error:
        if error.code != 409: raise
    for key, kind, size in [('farm_id','string',36),('code','string',8),('sequence','integer',None),('batch_no','string',225)]:
        ensure(db,database,COLLECTION,key,kind,size)
    ensure(db,database,crops,'batch_code','string',8)
    for collection in (batches,records):
        for key,size in [('import_source_id',225),('import_fingerprint',64),('source_data',16384)]:
            ensure(db,database,collection,key,'string',size)
        ensure(db,database,collection,'historical_import','boolean')
    for key in ('plant_height_cm','leaf_count','nutrient_solution_ml','water_volume_litres'):
        ensure(db,database,records,key,'float')
    for key in ('water_source','water_purpose'):
        ensure(db,database,records,key,'string',225)
    for key in ('total_seeds_nursed','total_transplanted','total_harvested'):
        field = db.get_attribute(database,batches,key)
        if field.get('required'):
            update_attribute(database,batches,'integer',key,{'required':False,'default':None})
    field = db.get_attribute(database,batches,'total_weight_kg')
    if field.get('required'): update_attribute(database,batches,'float','total_weight_kg',{'required':False,'default':None})
    field = db.get_attribute(database,batches,'production_status')
    elements = field['elements']
    if 'Unknown' not in elements:
        update_attribute(database,batches,'enum','production_status',{'elements':elements+['Unknown'],'required':True,'default':None})
    for key in ('total_seeds_nursed','total_transplanted','total_harvested','total_weight_kg','production_status'):
        for _ in range(45):
            attribute = db.get_attribute(database,batches,key)
            if attribute['status'] == 'available': break
            time.sleep(1)
        else: raise RuntimeError('Updated attribute not ready: ' + key)
        if key != 'production_status' and (attribute['required'] or attribute.get('default') is not None):
            raise RuntimeError('Quantity must remain nullable: ' + key)
    print('Cultivation import and numbering schema ready; existing values preserved.')


def update_attribute(database, collection, kind, key, payload):
    # This installed SDK removes top-level None parameters. The API requires an
    # explicit JSON null for default; never replace it with an invented zero.
    path = '/databases/{}/collections/{}/attributes/{}/{}'.format(*[
        quote(value, safe='') for value in (database,collection,kind,key)])
    response = requests.patch(os.environ['APPWRITE_ENDPOINT'].rstrip('/') + path,
        headers={'X-Appwrite-Project':os.environ['APPWRITE_PROJECT_ID'],
                 'X-Appwrite-Key':os.environ['APPWRITE_API_KEY']},
        json=payload, timeout=30)
    if not response.ok:
        raise RuntimeError(f'Attribute update failed ({response.status_code}): {response.json().get("message", key)}')


if __name__ == '__main__': migrate()
