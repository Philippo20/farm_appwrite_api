"""Immutable calibration history. Queued events never update the live heartbeat."""
import json
import os
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query as ApiQuery
from appwrite.query import Query
from appwrite.exception import AppwriteException
from db import db
from main import db_id
from routes.messaging import current_member
from routes.command_devices import sensor_for, authorize
from routes.light_switches import authorize_device, get_doc, write_doc, key
from switch_control import now_utc
from calibration_events import CalibrationEvent, PHASE, TERMINAL, session_view, notification_for
from workflow_notifications import publish_event

router = APIRouter(prefix='/command-devices', tags=['Device calibration'])
COLLECTION = os.getenv('APPWRITE_CALIBRATION_EVENTS_COLLECTION', 'calibration_events')

def read_event(identity):
    try:
        return db.get_document(db_id, COLLECTION, identity)
    except AppwriteException as error:
        if error.code == 404:
            return None
        raise

def command_for(identity, sensor, session):
    command = get_doc(key('y', identity))
    if (not command or command.get('sensor_id') != sensor['$id'] or command.get('session_id') != session):
        raise HTTPException(409, 'The event command does not belong to this device and boot session.')
    claimed = get_doc(command['slot'])
    if not claimed or claimed.get('id') != identity:
        raise HTTPException(409, 'The event must reference a dispatched command.')
    return command

def public_event(row):
    return {**json.loads(row['payload']), 'received_at': row['received_at'],
        'selection_at': row['selection_at']}

@router.post('/{serial}/events')
def ingest(serial: str, body: CalibrationEvent, x_sensor_key: str | None = Header(None)):
    sensor = sensor_for(serial)
    authorize_device(sensor, x_sensor_key)
    event = body.model_dump(mode='json')
    identity = event['event_id']
    payload = json.dumps(event, sort_keys=True, separators=(',', ':'))
    existing = read_event(identity)
    if existing and (existing['sensor_id'] != sensor['$id'] or existing['payload'] != payload):
        raise HTTPException(409, 'This event_id has already been used with different data.')
    selection = command_for(event['calibration_id'], sensor, event['session_id'])
    trigger = command_for(event['command_id'], sensor, event['session_id'])
    if trigger['created_at'] < selection['created_at']:
        raise HTTPException(409, 'The triggering command predates this calibration selection.')
    binding = {'calibration_id': event['calibration_id'], 'session_id': event['session_id'],
        'target': event['target'], 'rack': event['rack'], 'selection_at': selection['created_at']}
    binding_id = key('c', 'calibration:' + event['calibration_id'])
    if not write_doc(binding_id, sensor['$id'], 'calibration_binding', binding):
        if get_doc(binding_id) != binding:
            raise HTTPException(409, 'Calibration target, rack and boot session cannot change.')
    terminal_key = key('t', 'calibration:' + event['calibration_id'])
    terminal = get_doc(terminal_key)
    if event['type'] in TERMINAL:
        result = {name: event.get(name) for name in ('event_id', 'type', 'uptime_ms', 'saved_duration_ms')}
        if not write_doc(terminal_key, sensor['$id'], 'calibration_result', result):
            if get_doc(terminal_key) != result:
                raise HTTPException(409, 'This calibration already has a different final result. Start a new selection.')
    elif terminal and event['type'] != 'calibration.rejected' and event['uptime_ms'] > terminal['uptime_ms']:
        raise HTTPException(409, 'Progress cannot occur after the final result of this calibration.')
    duplicate = existing is not None
    if existing is None:
        try:
            db.create_document(db_id, COLLECTION, identity, data={
                'sensor_id': sensor['$id'], 'calibration_id': event['calibration_id'],
                'selection_at': selection['created_at'], 'uptime_ms': event['uptime_ms'],
                'phase': PHASE[event['type']], 'saved': event['saved'],
                'target': event['target'], 'rack': event['rack'] or '-',
                'payload': payload, 'received_at': now_utc().isoformat()}, permissions=[])
        except AppwriteException as error:
            if error.code != 409:
                raise
            existing = read_event(identity)
            duplicate = True
    if existing and (existing['sensor_id'] != sensor['$id'] or existing['payload'] != payload):
        raise HTTPException(409, 'This event_id has already been used with different data.')
    notification = notification_for(event, sensor, selection['actor_id'])
    if notification:
        try:
            # Recipient-scoped deterministic IDs make duplicate and partial
            # delivery retries safe, including concurrent requests.
            publish_event('calibration:' + identity, notification)
        except Exception:
            logging.getLogger(__name__).exception('Calibration notification delivery deferred')
            raise HTTPException(503, 'Event saved. Retry the same event_id to finish notification delivery.') from None
    return {'accepted': True, 'duplicate': duplicate, 'event_id': identity}

def rows_for(sensor_id, *filters, limit=100, before=None):
    return db.list_documents(db_id, COLLECTION, queries=[
        Query.equal('sensor_id', [sensor_id]), *filters,
        Query.order_desc('selection_at'), Query.order_desc('uptime_ms'),
        Query.order_desc('phase'), Query.order_desc('$id'), Query.limit(limit),
        *([Query.cursor_after(before)] if before else [])])['documents']

@router.get('/{serial}/calibrations')
def overview(serial: str, actor=Depends(current_member)):
    sensor = sensor_for(serial)
    authorize(actor, sensor)
    rows = rows_for(sensor['$id'])
    events = [public_event(row) for row in rows]
    grouped = {}
    for event in events:
        grouped.setdefault(event['calibration_id'], []).append(event)
    sessions = [session_view(group) for group in grouped.values()]
    # A failed new selection must not hide an existing running calibration.
    current = next((s for s in sessions if s['status'] != 'rejected'), sessions[0] if sessions else None)
    saved = []
    for target, rack in [('ef_drain', '-'), ('p_drain', '-'), ('fertigation', 'E'), ('fertigation', 'F'), ('fertigation', 'P')]:
        values = rows_for(sensor['$id'], Query.equal('saved', [True]),
            Query.equal('target', [target]), Query.equal('rack', [rack]), limit=1)
        if values:
            saved.append(public_event(values[0]))
    return {'current': current, 'latest_attempt': sessions[0] if sessions else None,
        'saved_durations': saved, 'recent_events': events[:10],
        'next_cursor': rows[9]['$id'] if len(rows) > 10 else None}

@router.get('/{serial}/calibrations/events')
def history(serial: str, before: UUID | None = None,
            calibration_id: UUID | None = None, limit: int = ApiQuery(25, ge=1, le=50),
            actor=Depends(current_member)):
    sensor = sensor_for(serial)
    authorize(actor, sensor)
    if before:
        cursor = read_event(str(before))
        if (not cursor or cursor['sensor_id'] != sensor['$id'] or
                (calibration_id and cursor['calibration_id'] != str(calibration_id))):
            raise HTTPException(404, 'History cursor not found for this device.')
    filters = [Query.equal('calibration_id', [str(calibration_id)])] if calibration_id else []
    rows = rows_for(sensor['$id'], *filters, limit=limit + 1, before=str(before) if before else None)
    page = rows[:limit]
    return {'events': [public_event(row) for row in page],
        'next_cursor': page[-1]['$id'] if len(rows) > limit else None}
