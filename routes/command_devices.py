"""Farm-scoped commands with explicit board acknowledgement and exclusive slots."""
from datetime import timedelta
from typing import Annotated
from uuid import UUID
import json
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, StrictBool
from appwrite.query import Query
from audit_utils import write_audit
from db import db
from main import db_id, db_collection_id11
from routes.messaging import current_member
from routes.light_switches import key, get_doc, write_doc, authorize_device, COLLECTION
from switch_control import now_utc, online, command_live, parse_time, can_control, COMMAND_SECONDS
from device_maintenance import can_manage
from device_commands import configured_commands, config_revision

router = APIRouter(prefix='/command-devices', tags=['Command devices'])
OFFLINE_SECONDS = 5.5

def sensor_for(serial):
    rows = db.list_documents(db_id, db_collection_id11,
        queries=[Query.equal('serial_number', [serial]), Query.limit(2)])['documents']
    if len(rows) != 1 or rows[0].get('sensortype') != 'command_device':
        raise HTTPException(404, 'Registered command device not found.')
    return rows[0]

def latest(sensor_id):
    rows = db.list_documents(db_id, COLLECTION, queries=[Query.equal('sensor_id', [sensor_id]),
        Query.equal('kind', ['device_command']), Query.order_desc('$createdAt'), Query.order_desc('$id'), Query.limit(1)])['documents']
    return json.loads(rows[0]['payload']) if rows else None

def slot(sensor_id, session, sequence):
    return key('v', f'{sensor_id}:{session}:{sequence}')

def live(command, heartbeat, sensor, now):
    return bool(command_live(command, heartbeat, now) and
        command.get('sequence') == heartbeat.get('sequence') and
        command.get('config_revision') == config_revision(sensor) and sensor.get('status') == 'Active')

def authorize(actor, sensor, control=False):
    from main import db_collection_id2
    if actor.get('status') != 'Active':
        raise HTTPException(403, 'Your account is not active.')
    farm = db.get_document(db_id, db_collection_id2, sensor['farmID'])
    allowed = can_control(actor, farm)
    identities = {actor.get('$id'), actor.get('email')} - {None, ''}
    manager = actor.get('role') == 'farm_manager' and farm.get('farm_manager_id') in identities
    if not allowed and (control or not (can_manage(actor, farm) or manager)):
        raise HTTPException(403, 'This device is not assigned to you.')
    return allowed

def view(sensor, can_send=True):
    command = latest(sensor['$id'])
    ack = get_doc(key('z', command['id'])) if command else None
    # Read presence after command history: slow history queries must not age an
    # earlier heartbeat snapshot while the board is successfully polling.
    heartbeat = get_doc(key('j', sensor['$id']))
    now = now_utc()
    pending = bool(command and not ack and live(command, heartbeat, sensor, now))
    occupied = get_doc(slot(sensor['$id'], heartbeat['session_id'], heartbeat['sequence'])) if heartbeat else None
    status = None
    if command:
        status = ('confirmed' if ack['success'] else 'failed') if ack else 'pending' if pending else 'expired'
    return {'serial_number': sensor['serial_number'], 'online': online(heartbeat, now, timeout=OFFLINE_SECONDS),
        'offline_after_ms': OFFLINE_SECONDS * 1000,
        'enabled': sensor.get('status') == 'Active', 'pending': pending, 'can_send': can_send,
        'ready': can_send and online(heartbeat, now, timeout=OFFLINE_SECONDS) and sensor.get('status') == 'Active' and not occupied,
        'commands': configured_commands(sensor.get('command_config')),
        'config_revision': config_revision(sensor),
        'controller_session_id': heartbeat.get('session_id') if heartbeat else None,
        'seen_at': heartbeat.get('seen_at') if heartbeat else None, 'server_time': now.isoformat(),
        'last_command': {**{k: command[k] for k in ('id', 'label', 'value', 'created_at', 'expires_at', 'session_id')},
            'status': status, 'result': ack.get('message') if ack else None,
            'confirmed_at': ack.get('at') if ack else None} if command else None}

class Send(BaseModel):
    command_key: str = Field(min_length=1, max_length=36)
    request_id: UUID
    config_revision: str = Field(min_length=64, max_length=64)

class Poll(BaseModel):
    session_id: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    sequence: Annotated[int, Field(strict=True, ge=0, le=2147483647)]

class Ack(Poll):
    command_id: UUID
    success: StrictBool
    message: str = Field(default='', max_length=256)

@router.get('/{serial}/state')
def state(serial: str, actor=Depends(current_member)):
    sensor = sensor_for(serial)
    allowed = authorize(actor, sensor)
    return view(sensor, allowed)

@router.post('/{serial}/commands')
def send(serial: str, body: Send, actor=Depends(current_member)):
    sensor = sensor_for(serial)
    authorize(actor, sensor, control=True)
    profile = actor
    request_id = str(body.request_id)
    existing = get_doc(key('y', request_id))
    if existing:
        if (existing.get('sensor_id') != sensor['$id'] or existing.get('actor_id') != profile['$id']
                or existing.get('command_key') != body.command_key):
            raise HTTPException(409, 'Request ID already used.')
        claimed = get_doc(existing['slot'])
        if claimed:
            if claimed['id'] != request_id:
                raise HTTPException(409, 'Another command occupies this device slot.')
            return view(sensor)
        command = existing
    else:
        if body.config_revision != config_revision(sensor):
            raise HTTPException(409, 'The command configuration changed. Refresh the device and select the command again.')
        heartbeat = get_doc(key('j', sensor['$id']))
        if sensor.get('status') != 'Active':
            raise HTTPException(409, 'Activate this device before sending commands.')
        if not online(heartbeat, now_utc(), timeout=OFFLINE_SECONDS):
            raise HTTPException(409, 'The command device is offline.')
        definition = next((item for item in configured_commands(sensor.get('command_config'))
                           if item['id'] == body.command_key), None)
        if definition is None:
            raise HTTPException(422, 'Choose a command configured for this device.')
        now = now_utc()
        command = {'id': request_id, 'sensor_id': sensor['$id'], 'actor_id': profile['$id'],
            'command_key': body.command_key, 'label': definition['label'], 'value': definition['value'],
            'session_id': heartbeat['session_id'], 'sequence': heartbeat['sequence'],
            'slot': slot(sensor['$id'], heartbeat['session_id'], heartbeat['sequence']),
            'config_revision': config_revision(sensor), 'created_at': now.isoformat(),
            'expires_at': (now + timedelta(seconds=COMMAND_SECONDS)).isoformat()}
        if not write_doc(key('y', request_id), sensor['$id'], 'device_request', command):
            raise HTTPException(409, 'Request is already being submitted. Refresh its status.')
    heartbeat = get_doc(key('j', sensor['$id']))
    if not live(command, heartbeat, sensor, now_utc()):
        raise HTTPException(409, 'This command request is no longer valid. Refresh the device.')
    if not write_doc(command['slot'], sensor['$id'], 'device_command', command):
        claimed = get_doc(command['slot'])
        if not claimed or claimed['id'] != request_id:
            raise HTTPException(409, 'A command is already awaiting device confirmation.')
    else:
        write_audit(action_type='Update', collection_name='Command devices',
            performed_by_id=profile['$id'], performed_by_role=profile['role'],
            action_details=f"Sent {command['label']} to {serial}",
            new_data={'id': request_id, 'serial': serial, 'command': command['value']})
    return view(sensor)

@router.post('/{serial}/poll')
def poll(serial: str, body: Poll, x_sensor_key: str | None = Header(None)):
    sensor = sensor_for(serial)
    authorize_device(sensor, x_sensor_key)
    now = now_utc()
    heartbeat = {**body.model_dump(), 'seen_at': now.isoformat()}
    write_doc(key('j', sensor['$id']), sensor['$id'], 'device_heartbeat', heartbeat, replace=True)
    command = get_doc(slot(sensor['$id'], body.session_id, body.sequence))
    if not command:
        return {'command': None, 'advance_sequence': False}
    if get_doc(key('z', command['id'])) or not live(command, heartbeat, sensor, now):
        return {'command': None, 'advance_sequence': True}
    return {'command': {k: command[k] for k in ('id', 'command_key', 'label', 'value', 'sequence')},
            'valid_for_ms': max(0, int((parse_time(command['expires_at']) - now).total_seconds()*1000)),
            'advance_sequence': False}

@router.post('/{serial}/ack')
def acknowledge(serial: str, body: Ack, x_sensor_key: str | None = Header(None)):
    sensor = sensor_for(serial)
    authorize_device(sensor, x_sensor_key)
    command = get_doc(slot(sensor['$id'], body.session_id, body.sequence))
    if not command or command['id'] != str(body.command_id):
        raise HTTPException(409, 'Command does not belong to this device session and sequence.')
    receipt = get_doc(key('z', command['id']))
    if receipt:
        if receipt['success'] != body.success or receipt['message'] != body.message:
            raise HTTPException(409, 'The command result has already been recorded.')
        return {'accepted': True}
    heartbeat = get_doc(key('j', sensor['$id']))
    if not live(command, heartbeat, sensor, now_utc()):
        raise HTTPException(409, 'The command has expired or the device configuration changed.')
    receipt = {'success': body.success, 'message': body.message, 'at': now_utc().isoformat()}
    if not write_doc(key('z', command['id']), sensor['$id'], 'device_ack', receipt):
        saved = get_doc(key('z', command['id']))
        if saved != receipt and (saved['success'] != body.success or saved['message'] != body.message):
            raise HTTPException(409, 'A different command result is already recorded.')
    return {'accepted': True}
