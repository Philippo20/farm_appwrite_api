import hashlib
import hmac
import json
import os
from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, StrictBool
from appwrite.query import Query
from appwrite.exception import AppwriteException
from auth import get_current_user
from db import db
from main import db_id, db_collection_id1, db_collection_id2, db_collection_id11
from switch_control import now_utc, parse_time, online, command_live, can_control, COMMAND_SECONDS

router = APIRouter(tags=['Light switches'])
COLLECTION = os.getenv('APPWRITE_SWITCH_CONTROL_COLLECTION', 'switch_control')

def key(kind, identity):
    return kind + hashlib.sha256(identity.encode()).hexdigest()[:30]

def get_doc(identity):
    try:
        doc = db.get_document(db_id, COLLECTION, identity)
        return json.loads(doc['payload'])
    except AppwriteException as error:
        if error.code == 404: return None
        raise

def write_doc(identity, sensor_id, kind, payload, replace=False):
    data = {'sensor_id': sensor_id, 'kind': kind, 'payload': json.dumps(payload)}
    try:
        db.create_document(db_id, COLLECTION, identity, data, permissions=[])
    except AppwriteException as error:
        if error.code != 409: raise
        if replace: db.update_document(db_id, COLLECTION, identity, data)
        else: return False
    return True

def latest_command(sensor_id):
    rows = db.list_documents(db_id, COLLECTION, queries=[Query.equal('sensor_id', [sensor_id]),
        Query.equal('kind', ['command']), Query.order_desc('$createdAt'), Query.order_desc('$id'), Query.limit(1)])['documents']
    return json.loads(rows[0]['payload']) if rows else None

def sensor_for(serial):
    rows = db.list_documents(db_id, db_collection_id11, queries=[Query.equal('serial_number', [serial]), Query.limit(2)])['documents']
    if len(rows) != 1 or rows[0].get('sensortype') != 'light_switch':
        raise HTTPException(404, 'Registered light switch not found')
    return rows[0]

def authorize_user(actor, sensor):
    profiles = db.list_documents(db_id, db_collection_id1, queries=[Query.equal('email', [actor.get('email', '')]), Query.limit(2)])['documents']
    farm = db.get_document(db_id, db_collection_id2, sensor['farmID'])
    if len(profiles) != 1 or not can_control(profiles[0], farm):
        raise HTTPException(403, 'You cannot control this farm equipment')
    return profiles[0]

def authorize_device(sensor, supplied):
    farm = db.get_document(db_id, db_collection_id2, sensor['farmID'])
    expected = str(farm.get('sensor_ingest_api_key') or '').strip()
    # Fail closed: controls require a farm-specific key, never a public fallback.
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, 'Invalid device key')

def view(sensor):
    sensor_id = sensor['$id']
    heartbeat = get_doc(key('h', sensor_id))
    command = latest_command(sensor_id)
    receipt = get_doc(key('a', command['id'])) if command else None
    now = now_utc()
    active = online(heartbeat, now)
    pending = command_live(command, heartbeat, now) and receipt is None
    state = heartbeat.get('reported_on') if heartbeat else None
    if receipt and heartbeat and receipt['session_id'] == heartbeat['session_id'] and parse_time(receipt['at']) >= parse_time(heartbeat['seen_at']):
        state = receipt['reported_on']
    return {'serial_number': sensor['serial_number'], 'online': active, 'reported_on': state,
            'pending': pending, 'desired_on': command['desired_on'] if pending else None,
            'command_id': command['id'] if command else None,
            'command_status': ('confirmed' if receipt and receipt['reported_on'] == command['desired_on'] else 'failed') if receipt else 'pending' if pending else 'expired' if command else None,
            'seen_at': heartbeat.get('seen_at') if heartbeat else None, 'server_time': now.isoformat()}

class Command(BaseModel):
    desired_on: StrictBool
    request_id: UUID

class Poll(BaseModel):
    session_id: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    reported_on: StrictBool

class Ack(Poll):
    command_id: UUID

@router.get('/switches/{serial}/state')
def state(serial: str, actor: dict = Depends(get_current_user)):
    sensor = sensor_for(serial)
    authorize_user(actor, sensor)
    return view(sensor)

@router.post('/switches/{serial}/commands')
def command(serial: str, body: Command, actor: dict = Depends(get_current_user)):
    sensor = sensor_for(serial)
    profile = authorize_user(actor, sensor)
    command_id = str(body.request_id)
    existing = get_doc(key('c', command_id))
    if existing:
        if existing['sensor_id'] != sensor['$id'] or existing['desired_on'] != body.desired_on or existing['actor_id'] != profile['$id']:
            raise HTTPException(409, 'Request ID already used')
        return view(sensor)
    heartbeat = get_doc(key('h', sensor['$id']))
    if not online(heartbeat, now_utc()): raise HTTPException(409, 'Light switch is offline')
    current = latest_command(sensor['$id'])
    if command_live(current, heartbeat, now_utc()) and not get_doc(key('a', current['id'])):
        raise HTTPException(409, 'A command is already awaiting confirmation')
    payload = {'id': command_id, 'sensor_id': sensor['$id'], 'session_id': heartbeat['session_id'],
        'desired_on': body.desired_on, 'actor_id': profile['$id'],
        'expires_at': (now_utc()+timedelta(seconds=COMMAND_SECONDS)).isoformat()}
    if not write_doc(key('c', command_id), sensor['$id'], 'command', payload):
        raise HTTPException(409, 'Command already submitted')
    return view(sensor)

@router.post('/switches/{serial}/poll')
def poll(serial: str, body: Poll, x_sensor_key: str | None = Header(None)):
    sensor = sensor_for(serial)
    authorize_device(sensor, x_sensor_key)
    now = now_utc()
    heartbeat = {'session_id': body.session_id, 'reported_on': body.reported_on, 'seen_at': now.isoformat()}
    write_doc(key('h', sensor['$id']), sensor['$id'], 'heartbeat', heartbeat, replace=True)
    command = latest_command(sensor['$id'])
    if not command_live(command, heartbeat, now) or get_doc(key('a', command['id'])):
        return {'command': None}
    return {'command': {'id': command['id'], 'desired_on': command['desired_on'],
        'valid_for_ms': max(0, int((parse_time(command['expires_at'])-now).total_seconds()*1000))}}

@router.post('/switches/{serial}/ack')
def acknowledge(serial: str, body: Ack, x_sensor_key: str | None = Header(None)):
    sensor = sensor_for(serial)
    authorize_device(sensor, x_sensor_key)
    command_id = str(body.command_id)
    command = get_doc(key('c', command_id))
    if not command or command['sensor_id'] != sensor['$id'] or command['session_id'] != body.session_id:
        raise HTTPException(409, 'Command does not belong to this device session')
    payload = {'command_id': command_id, 'session_id': body.session_id,
               'reported_on': body.reported_on, 'at': now_utc().isoformat()}
    write_doc(key('a', command_id), sensor['$id'], 'ack', payload)
    return {'accepted': True}
