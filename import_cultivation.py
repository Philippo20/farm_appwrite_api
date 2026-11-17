"""Admin-operated import. Dry run by default; source/report must stay outside Git.

Extract with scripts/extract_cultivation_workbook.py first. Run the schema migration
before --apply. Re-running the same input is safe; changed source rows are rejected.
"""
import argparse
import json
import os
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from cultivation_import import prepare, write_once, digest, DATASET
from document_paging import list_all_documents
from migrate_cultivation_import import connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--farm', required=True)
    parser.add_argument('--actor', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    db, database = connection()
    collections = {n: os.environ[f'APPWRITE_COLLECTION_ID{n}'] for n in (1, 2, 5, 6, 16, 24)}
    actor = db.get_document(database, collections[1], args.actor)
    if str(actor.get('status', '')).lower() != 'active':
        raise ValueError('Import actor must be active')
    roles = actor.get('roles') or [actor.get('role', '')]
    if isinstance(roles, str):
        try: roles = json.loads(roles)
        except ValueError: roles = [roles]
    if not any(str(r).lower().replace(' ', '').replace('_', '') in ('admin', 'superadmin') for r in roles):
        raise ValueError('Import actor must be an administrator')
    farm = db.get_document(database, collections[2], args.farm)
    crops = list_all_documents(db, database_id=database, collection_id=collections[16])['documents']
    source = json.loads(Path(args.source).read_text(encoding='utf-8'))
    result = prepare(source, farm, crops, actor, date.today())
    # Fail before writing if a changed source row would collide with a previous import.
    existing = {n: list_all_documents(db, database_id=database, collection_id=collections[n])['documents'] for n in (5, 24)}
    planned = [(5, b['batch_id'], b) for b in result['batches']] + [(24, r['id'], r['data']) for r in result['records']]
    for collection, key, payload in planned:
        for previous in existing[collection]:
            if previous['$id'] == key and (previous.get('import_fingerprint') != payload['import_fingerprint'] or previous.get('import_source_id') != payload['import_source_id']):
                raise ValueError('Source changed since previous import: ' + payload['import_source_id'])
            if collection == 5 and previous['$id'] != key and previous.get('batch_no') == payload['batch_no']:
                raise ValueError('Batch number already exists: ' + payload['batch_no'])
    summary = {'batches': len(result['batches']), 'records': len(result['records']),
               'held': len(result['held']), 'held_reasons': dict(Counter(r['reason'] for r in result['held'])),
               'skipped_placeholders': result['skipped_placeholders']}
    result['summary'] = summary
    result['journal'] = []
    report = Path(args.report)
    def save(): report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    print(json.dumps(summary), flush=True)
    if not args.apply: return
    now = datetime.now(timezone.utc).isoformat()
    schemas = {n: {a['key']: a for a in db.get_collection(database, collections[n])['attributes']} for n in (5, 24)}
    for collection, key, payload in planned:
        payload.update(created_at=now, updated_at=now)
        for field, value in payload.items():
            attribute = schemas[collection].get(field)
            if not attribute or attribute.get('status') != 'available':
                raise ValueError('Run migration first: ' + field)
            if value is None and attribute['required']:
                raise ValueError('Required field cannot remain unknown: ' + field)
            if isinstance(value, str) and attribute.get('size') and len(value) > attribute['size']:
                raise ValueError(f'Source text exceeds field capacity: {key}/{field}')
    # Set only the four matched crop codes; preserve unrelated catalog data.
    for batch in result['batches']:
        crop = next(c for c in crops if c['$id'] == batch['crop_variety_id'])
        code = batch['batch_no'].split()[0]
        if crop.get('batch_code') not in (None, '', code): raise ValueError('Conflicting existing variety code')
        if any(c['$id'] != crop['$id'] and c.get('batch_code') == code for c in crops): raise ValueError('Duplicate variety code')
    for crop in crops:
        matching = next((b for b in result['batches'] if b['crop_variety_id'] == crop['$id']), None)
        if matching:
            db.update_document(database, collections[16], crop['$id'], {'batch_code': matching['batch_no'].split()[0]})
    for index, (collection, key, payload) in enumerate(planned):
        payload.update(created_at=now, updated_at=now)
        state = write_once(db, database, collections[collection], key, payload)
        result['journal'].append({'collection': collection, 'id': key, 'state': state})
        save()
        if (index + 1) % 50 == 0: print(f'Processed {index + 1}/{len(planned)}', flush=True)
    # One administrative audit entry; deliberately do not replay historic notifications.
    audit_id = digest(DATASET + '|audit|' + digest(source))[:36]
    from appwrite.exception import AppwriteException
    try:
        db.create_document(database, collections[6], audit_id, {
            'audit_id': audit_id, 'action_type': 'Create', 'collection_name': 'Cultivation import',
            'performed_by_id': actor['$id'], 'performed_by_role': 'superadmin' if 'superadmin' in roles else 'admin', 'timestamp': now,
            'action_details': f"Imported {summary['batches']} historical batches and {summary['records']} records; {summary['held']} held for review.",
            'ip_address': '', 'status': 'Success', 'previous_data': '',
            'new_data': json.dumps({k: summary[k] for k in ('batches', 'records', 'held')}),
        })
    except AppwriteException as error:
        if error.code != 409: raise
    # Read back all written rows, not just successful HTTP acknowledgments.
    for collection in (5, 24):
        docs = {d['$id']: d for d in list_all_documents(db, database_id=database, collection_id=collections[collection])['documents']}
        for target, key, payload in planned:
            if target == collection and docs.get(key, {}).get('import_fingerprint') != payload['import_fingerprint']:
                raise RuntimeError('Read-back verification failed: ' + key)
    result['verified'] = True
    save()
    print('Verified all imported documents. ' + json.dumps(dict(Counter(r['state'] for r in result['journal']))))


if __name__ == '__main__': main()
