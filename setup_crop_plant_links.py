"""Create crop parent links; backfill only unambiguous exact legacy names."""
import time
from appwrite.exception import AppwriteException
from db import db
from main import db_id, db_collection_id3, db_collection_id16
from document_paging import list_all_documents
from crop_relationships import exact_legacy_plant


def setup():
    try:
        db.create_string_attribute(db_id, db_collection_id16, 'plant_type_ID', 36, False)
    except AppwriteException as error:
        if error.code != 409:
            raise
    for _ in range(45):
        field = db.get_attribute(db_id, db_collection_id16, 'plant_type_ID')
        if field.get('status') == 'available':
            if field.get('type') != 'string' or field.get('array') or field.get('size', 0) < 36:
                raise RuntimeError('Incompatible crop plant_type_ID attribute.')
            break
        if field.get('status') in {'failed', 'stuck'}:
            raise RuntimeError('Crop plant_type_ID attribute failed.')
        time.sleep(1)
    else:
        raise RuntimeError('Crop plant_type_ID still processing; rerun migration.')
    plants = list_all_documents(db, database_id=db_id, collection_id=db_collection_id3)['documents']
    crops = list_all_documents(db, database_id=db_id, collection_id=db_collection_id16)['documents']
    linked, unresolved = 0, 0
    for crop in crops:
        if crop.get('plant_type_ID'):
            continue
        plant = exact_legacy_plant(crop, plants)
        if plant and str(plant.get('status', 'active')).lower() == 'active':
            db.update_document(db_id, db_collection_id16, crop['$id'], {'plant_type_ID': plant['$id']})
            linked += 1
        else:
            unresolved += 1
    print(f'Crop plant links ready. Linked {linked} exact matches; {unresolved} varieties need manual plant selection.')


if __name__ == '__main__':
    setup()
