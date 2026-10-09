"""Add farm variety IDs and migrate only unique existing catalog matches."""
import time
from appwrite.exception import AppwriteException
from db import db
from main import db_id, db_collection_id2, db_collection_id3, db_collection_id5, db_collection_id16
from document_paging import list_all_documents
from crop_relationships import exact_legacy_plant, plant_key, variety_matches_plant


def setup():
    for collection, key, size, array in [
            (db_collection_id2, 'plant_type_ID', 36, False),
            (db_collection_id2, 'crop_variety_ids', 36, True),
            (db_collection_id2, 'plant_varieties', 225, True),
            (db_collection_id5, 'crop_variety_id', 36, False)]:
        try:
            db.create_string_attribute(db_id, collection, key, size, False, array=array)
        except AppwriteException as error:
            if error.code != 409: raise
        for _ in range(45):
            field = db.get_attribute(db_id, collection, key)
            if field.get('status') == 'available':
                if field.get('type') != 'string' or bool(field.get('array')) != array or field.get('size', 0) < size:
                    raise RuntimeError(f'Incompatible {key} attribute.')
                break
            if field.get('status') in {'failed', 'stuck'}: raise RuntimeError(f'{key} attribute failed.')
            time.sleep(1)
        else: raise RuntimeError(f'{key} still processing; rerun migration.')
    plants = list_all_documents(db, database_id=db_id, collection_id=db_collection_id3)['documents']
    crops = list_all_documents(db, database_id=db_id, collection_id=db_collection_id16)['documents']
    farms = list_all_documents(db, database_id=db_id, collection_id=db_collection_id2)['documents']
    linked, unresolved = 0, 0
    for farm in farms:
        if farm.get('crop_variety_ids'): continue
        plant = next((p for p in plants if p['$id'] == farm.get('plant_type_ID')), None) if farm.get('plant_type_ID') else exact_legacy_plant({'crop_name': farm.get('plant_type')}, plants)
        matches = [c for c in crops if plant and variety_matches_plant(c, plant['$id'], plant['name']) and
                   plant_key(c.get('variety_name')) == plant_key(farm.get('plant_variety'))]
        if len(matches) == 1:
            crop = matches[0]
            db.update_document(db_id, db_collection_id2, farm['$id'], {'plant_type_ID': plant['$id'],
                'crop_variety_ids': [crop['$id']], 'plant_varieties': [crop['variety_name']]})
            linked += 1
        else: unresolved += 1
    print(f'Farm variety fields ready. Preserved {linked} catalog assignments; {unresolved} farms need manual variety selection.')


if __name__ == '__main__': setup()
