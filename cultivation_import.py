"""Validated, deterministic historical import. No notifications or progress mutations."""
import hashlib
import json
import math
import re
from datetime import date, timedelta
from batch_numbers import parse_number

DATASET = 'farm-estates-cultivation-v1'
SUPPLIERS = {
    'rijk zwaana - batavia': ('Batavia', 'BL'),
    'rijk zwaana - concorde': ('Lolorosa', 'LL'),
    'technisem - eden': ('Eden', 'EL'),
    'technisem - oak': ('Oak Red', 'RO'),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def identity(sheet, row):
    return digest(f'{DATASET}|{sheet}|{row}')[:36]


def numeric(value, integer=False):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0 or (integer and not result.is_integer()):
        raise ValueError(f'Invalid nonnegative measurement: {value}')
    return int(result) if integer else result


def provenance(sheet, row, values):
    source = {'sheet': sheet, 'row': row, 'values': values}
    return {'import_source_id': f'{DATASET}/{sheet}/{row}',
            'import_fingerprint': digest(source), 'source_data': json.dumps(source, ensure_ascii=False),
            'historical_import': True}


def day(value):
    if not value: raise ValueError('Missing observation or seeding date')
    return date.fromisoformat(str(value)[:10])


def prepare(source, farm, crops, actor, today):
    """Dates/supplier columns win. Ambiguous observations are retained in held[]."""
    result = {'batches': [], 'records': [], 'held': [], 'aliases': [], 'skipped_placeholders': 0}
    originals, counters = {}, {}
    def hold(sheet, row, values, reason):
        result['held'].append({'sheet': sheet, 'row': row, 'reason': str(reason), 'values': values})
    for row in source['Batch Register']:
        values, number = row['values'], row['row']
        if not values[0]: continue
        try:
            original = str(values[0]).strip()
            if original in originals: raise ValueError('Duplicate workbook batch number')
            parsed = parse_number(original)
            if not parsed: raise ValueError('Unrecognized batch number')
            name, code = SUPPLIERS[str(values[1]).strip().lower()]
            matches = [c for c in crops if c.get('variety_name') == name and
                       c['$id'] in farm.get('crop_variety_ids', [])]
            if len(matches) != 1: raise ValueError('Variety not uniquely assigned to this farm')
            crop = matches[0]
            start = day(values[2])
            if start > today: raise ValueError('Future seeding date')
            sequence = max(counters.get(code, 0) + 1, parsed[2])
            counters[code] = sequence
            batch_no = f'{code} {start:%d-%m-%Y}-{sequence}'
            harvested = day(values[6]) if values[6] else None
            if harvested and not start <= harvested <= today: raise ValueError('Invalid actual harvest date')
            payload = {
                'batch_id': identity('Batch Register', number), 'batch_no': batch_no,
                'farmID': farm['$id'], 'farm_name': farm['name'],
                'plant_type_ID': crop['plant_type_ID'], 'plant_name': farm['plant_type'],
                'plant_variety': name, 'crop_variety_id': crop['$id'],
                'farm_manager_id': farm.get('farm_manager_id') or '', 'farm_manager_name': '',
                # Do not attribute historical observations to today's caretakers.
                'caretaker_id': '', 'caretaker_name': '',
                'start_date': start.isoformat(), 'end_date': (start + timedelta(days=56)).isoformat(),
                'actual_harvest_date': harvested.isoformat() if harvested else None,
                'total_seeds_nursed': numeric(values[7], True),
                'total_transplanted': numeric(values[14], True),
                'total_harvested': numeric(values[15], True), 'total_weight_kg': None,
                'production_status': 'Harvested' if harvested else 'Unknown',
                'technical_issues': str(values[19] or ''),
                'inputs_supplied': 'Historical workbook import', 'funds_requested': False,
                'financial_status': 'Pending', 'fund_request_id': '',
                'delivery_status': 'Pending', 'delivery_details': '', 'harvest_images': '',
                'created_by': actor['$id'], **provenance('Batch Register', number, values),
            }
            result['batches'].append(payload)
            originals[original] = payload
            result['aliases'].append({'original': original, 'batch_number': batch_no, 'row': number})
        except (ValueError, KeyError, TypeError) as error:
            hold('Batch Register', number, values, error)

    def resolve(raw):
        key = str(raw or '').strip()
        if key in originals: return originals[key]
        # Normalize padding/year formatting without changing a sequence or date.
        parsed = parse_number(key)
        candidates = [b for original, b in originals.items() if parsed and parse_number(original) == parsed]
        if not candidates:
            # Missing sequence is safe only when the original code/date uniquely identifies a register row.
            match = re.fullmatch(r'([A-Z]+) (\d{1,2}-\d{1,2}-\d{4})', key)
            if match:
                base = parse_number(key + '-1')
                candidates = [b for original, b in originals.items() if parse_number(original)[:2] == base[:2]]
        if len(candidates) != 1: raise ValueError('Missing or ambiguous batch reference')
        return candidates[0]

    for sheet in ('Daily Growth Log', 'Nutrient & EC Log'):
        for row in source[sheet]:
            values, number = row['values'], row['row']
            relevant = values[3:7] if sheet == 'Daily Growth Log' else values[2:9] + values[10:11]
            if not any(v is not None and v != '' for v in relevant):
                result['skipped_placeholders'] += 1
                continue
            try:
                recorded = day(values[0])
                if recorded > today: raise ValueError('Future observation date')
                batch = resolve(values[1])
                if recorded < day(batch['start_date']): raise ValueError('Observation precedes authoritative seeding date')
                payload = {
                    'record_id': 'XLS-' + identity(sheet, number)[:12],
                    'farm_id': farm['$id'], 'farm_name': farm['name'],
                    'batch_id': batch['batch_id'], 'batch_number': batch['batch_no'],
                    'record_type': 'daily_monitoring' if sheet == 'Daily Growth Log' else 'watering',
                    'record_date': recorded.isoformat() + 'T00:00:00+00:00',
                    'created_by': actor['$id'], 'created_by_name': 'Historical import',
                    'growth_stage': '', 'plant_health': '', 'observations': '', 'activities_performed': '',
                    'has_issues': False, 'issue_description': '', 'issue_severity': 'none',
                    'notes': f'Imported from {sheet}, row {number}. Original batch: {values[1]}.',
                    **provenance(sheet, number, values),
                }
                if sheet == 'Daily Growth Log':
                    payload.update(plant_height_cm=numeric(values[3]), leaf_count=numeric(values[4], True),
                                   plant_health=str(values[5] or ''), observations=str(values[6] or ''))
                    if 'tip burn' in payload['plant_health'].lower():
                        payload.update(has_issues=True, issue_description=payload['plant_health'], issue_severity='low')
                else:
                    payload.update(ec=numeric(values[2]), ph=numeric(values[3]),
                        water_temperature=numeric(values[4]), nutrient_solution_ml=numeric(values[5]),
                        water_source=str(values[6] or ''), water_volume_litres=numeric(values[7]),
                        water_purpose=str(values[8] or ''), observations=str(values[10] or ''))
                    if payload['ph'] is not None and payload['ph'] > 14: raise ValueError('pH exceeds 14; review source')
                result['records'].append({'id': identity(sheet, number), 'data': payload})
            except (ValueError, KeyError, TypeError) as error:
                hold(sheet, number, values, error)
    return result


def write_once(db, database, collection, document_id, data):
    """Create once; conflict with altered provenance is an error, never an overwrite."""
    from appwrite.exception import AppwriteException
    try:
        db.create_document(database, collection, document_id, data)
        return 'created'
    except AppwriteException as error:
        if error.code != 409: raise
        previous = db.get_document(database, collection, document_id)
        if previous.get('import_fingerprint') != data.get('import_fingerprint') or previous.get('import_source_id') != data.get('import_source_id'):
            raise ValueError(f'Changed import source or ID collision: {document_id}') from error
        return 'existing'
