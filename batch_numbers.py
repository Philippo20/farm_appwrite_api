"""Server allocated variety/date/sequence numbers, unique across farms."""
import hashlib
import re
from datetime import date
from appwrite.exception import AppwriteException

COLLECTION = 'batch_number_reservations'
NUMBER = re.compile(r'^([A-Z0-9]{1,8})\s+(\d{1,2})-(\d{1,2})-(\d{2}|\d{4})-(\d+)$', re.I)


def clean_code(value):
    code = str(value or '').strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9]{0,7}', code):
        raise ValueError('Set a batch code of 1–8 letters/numbers, starting with a letter, on this crop variety.')
    return code


def parse_number(value):
    match = NUMBER.fullmatch(str(value or '').strip())
    if not match:
        return None
    code, day, month, year, sequence = match.groups()
    year = int(year) + (2000 if len(year) == 2 else 0)
    try:
        start = date(year, int(month), int(day))
    except ValueError:
        return None
    return code.upper(), start, int(sequence)


def reservation_id(farm_id, code, sequence):
    # Batch numbers are used outside farm-scoped views (deliveries/traceability).
    return hashlib.sha256(f'{code}|{sequence}'.encode()).hexdigest()[:36]


def allocate_number(db, database, farm_id, code, start, batches, reservations):
    code = clean_code(code)
    parsed = [parse_number(b.get('batch_no')) for b in batches]
    maximum = max([n[2] for n in parsed if n and n[0] == code] +
                  [int(r['sequence']) for r in reservations if r.get('code') == code] + [0])
    for sequence in range(maximum + 1, maximum + 101):
        number = f'{code} {start:%d-%m-%Y}-{sequence}'
        try:
            db.create_document(database_id=database, collection_id=COLLECTION,
                document_id=reservation_id(farm_id, code, sequence),
                data={'farm_id': farm_id, 'code': code, 'sequence': sequence, 'batch_no': number})
            return number
        except AppwriteException as error:
            if error.code != 409:
                raise
    raise RuntimeError('Could not reserve a batch number. Please retry.')
