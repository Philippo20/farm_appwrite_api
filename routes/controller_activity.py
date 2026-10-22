"""Durable activity history; current state is selected by boot and numeric generation."""
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, Query as ApiQuery
from appwrite.query import Query
from appwrite.exception import AppwriteException
from db import db
from main import db_id, db_collection_id11
from routes.messaging import current_member
from routes.command_devices import sensor_for, authorize, OFFLINE_SECONDS
from routes.light_switches import authorize_device, get_doc, key
from switch_control import online, now_utc, parse_time
from controller_activity import ControllerActivityEvent, activity_key, output_value, reported_elapsed

router = APIRouter(tags=['Controller activity'])
COLLECTION = os.getenv('APPWRITE_CONTROLLER_ACTIVITY_COLLECTION', 'controller_activity_events')

def public(row):
    return {**json.loads(row['payload']), 'received_at': row['received_at'], 'generation': row['generation']}

def ingest_activity(serial, body: ControllerActivityEvent, supplied_key):
    sensor = sensor_for(serial)
    authorize_device(sensor, supplied_key)
    payload = body.model_dump(mode='json')
    if body.command_id:
        from routes.calibration_events import command_for
        command_for(body.command_id, sensor, body.session_id)
    identity = activity_key(sensor['$id'], body.event_id)
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    duplicate = False
    alert = body.type == 'command.rejected' or (body.type == 'grid.changed' and not body.grid_available) or (body.type == 'rtc.changed' and not body.rtc_available)
    try:
        db.create_document(db_id, COLLECTION, identity, data={
            'sensor_id': sensor['$id'], 'event_id': body.event_id, 'session_id': body.session_id,
            'generation': body.generation, 'event_type': body.type,
            'payload': canonical, 'received_at': now_utc().isoformat(), 'notification_pending': alert}, permissions=[])
    except AppwriteException as error:
        if error.code != 409:
            raise
        saved = db.get_document(db_id, COLLECTION, identity)
        if saved['sensor_id'] != sensor['$id'] or saved['payload'] != canonical:
            raise HTTPException(409, 'This activity event_id already has different data.') from None
        duplicate = True
    # Events, including queued status reports, never renew board presence.
    return {'accepted': True, 'duplicate': duplicate, 'event_id': body.event_id}

def publish_pending_notifications():
    """Retry from durable history independently of the controller's HTTP queue."""
    from workflow_notifications import publish_event, ADMIN_ROLES
    rows = db.list_documents(db_id, COLLECTION, queries=[Query.equal('notification_pending', [True]),
        Query.order_asc('received_at'), Query.limit(50)])['documents']
    for row in rows:
        try:
            sensor = db.get_document(db_id, db_collection_id11, row['sensor_id'])
        except AppwriteException as error:
            if error.code != 404: raise
            db.update_document(db_id, COLLECTION, row['$id'], {'notification_pending': False})
            continue
        event = public(row)
        description = event['message'] or (event.get('reason') or event['type']).replace('_', ' ')
        publish_event('controller:' + row['$id'], {
            'title': 'Controller alert', 'message': f"{sensor['serial_number']}: {description}",
            'kind': 'sensor_alert', 'priority': 'high', 'roles': ADMIN_ROLES, 'farm': sensor['farmID']})
        db.update_document(db_id, COLLECTION, row['$id'], {'notification_pending': False})

async def notification_loop():
    import asyncio
    import logging
    while True:
        try:
            await asyncio.to_thread(publish_pending_notifications)
        except Exception:
            logging.getLogger(__name__).exception('Controller notification pass failed; will retry')
        await asyncio.sleep(10)

def current_snapshot(sensor):
    heartbeat = get_doc(key('j', sensor['$id']))
    snapshot = None
    if heartbeat:
        rows = db.list_documents(db_id, COLLECTION, queries=[Query.equal('sensor_id', [sensor['$id']]),
            Query.equal('session_id', [heartbeat['session_id']]), Query.order_desc('generation'), Query.limit(1)])['documents']
        snapshot = public(rows[0]) if rows else None
    # Refresh the heartbeat after history queries; a reboot during the query
    # invalidates this snapshot rather than reviving an earlier boot.
    current = get_doc(key('j', sensor['$id']))
    if snapshot and (not current or current['session_id'] != snapshot['session_id']):
        snapshot = None
    return {'snapshot': snapshot, **presence_view(sensor, current)}

def presence_view(sensor, current):
    now = now_utc()
    enabled = sensor.get('status') == 'Active'
    seen = parse_time((current or {}).get('seen_at'))
    return {'online': enabled and online(current, now, timeout=OFFLINE_SECONDS), 'enabled': enabled,
            'offline_after_ms': int(OFFLINE_SECONDS * 1000),
            'heartbeat_age_ms': max(0, int((now - seen).total_seconds() * 1000)) if seen else None,
            'seen_at': (current or {}).get('seen_at'),
            'controller_session_id': (current or {}).get('session_id'),
            'server_time': now.isoformat()}

@router.get('/command-devices/{serial}/activity')
def activity(serial: str, actor=Depends(current_member)):
    sensor = sensor_for(serial)
    authorize(actor, sensor)
    return current_snapshot(sensor)

@router.get('/command-devices/{serial}/activity/events')
def history(serial: str, before: str | None = None, limit: int = ApiQuery(25, ge=1, le=50), actor=Depends(current_member)):
    sensor = sensor_for(serial)
    authorize(actor, sensor)
    if before:
        try:
            cursor = db.get_document(db_id, COLLECTION, before)
        except AppwriteException as error:
            if error.code != 404: raise
            raise HTTPException(404, 'Activity cursor not found.') from None
        if cursor['sensor_id'] != sensor['$id']:
            raise HTTPException(404, 'Activity cursor belongs to another controller.')
    rows = db.list_documents(db_id, COLLECTION, queries=[Query.equal('sensor_id', [sensor['$id']]),
        Query.order_desc('received_at'), Query.order_desc('$id'), Query.limit(limit + 1),
        *([Query.cursor_after(before)] if before else [])])['documents']
    return {'events': [public(row) for row in rows[:limit]],
        'next_cursor': rows[limit - 1]['$id'] if len(rows) > limit else None}

@router.get('/controller-equipment')
def equipment(response: Response, device_id: list[str] = ApiQuery(..., min_length=1, max_length=100),
              presence_only: bool = False, status_only: bool = False, actor=Depends(current_member)):
    response.headers['Cache-Control'] = 'no-store'
    from routes.device_maintenance import history_for
    from device_maintenance import plans_for, schedule_view
    rows = db.list_documents(db_id, db_collection_id11, queries=[Query.equal('$id', list(set(device_id))), Query.limit(100)])['documents']
    controllers, result = {}, []
    for device in rows:
        controller_id = device.get('controller_id')
        if not controller_id:
            continue
        controller = controllers.get(controller_id)
        if controller is None:
            controller = db.get_document(db_id, db_collection_id11, controller_id)
            authorize(actor, controller)
            controllers[controller_id] = controller
        if controller.get('sensortype') != 'command_device' or controller.get('farmID') != device.get('farmID'):
            raise HTTPException(409, 'Equipment controller link needs review.')
        plans = plans_for(device) if not (presence_only or status_only) else []
        records = history_for(device['$id']) if plans else []
        tasks = [schedule_view(device, plan, records, datetime.now(timezone.utc).date()) for plan in plans]
        maintenance = next((s for s in ['Overdue', 'Due soon', 'Scheduled'] if any(t['status'] == s for t in tasks)), 'No scheduled maintenance')
        result.append({'device_id': device['$id'], 'controller_id': controller_id,
            'controller_serial': controller['serial_number'], 'output': device.get('controller_output'),
            **({'maintenance_status': maintenance,
            'next_due': min((t['due_date'] for t in tasks), default=None)} if not (presence_only or status_only) else {})})
    # One snapshot read per controller, shared by all of its registered outputs.
    states = {identity: ({'snapshot': None, **presence_view(controller, get_doc(key('j', identity)))}
        if presence_only and not status_only else current_snapshot(controller)) for identity, controller in controllers.items()}
    for item in result:
        state = states[item['controller_id']]
        snapshot = state['snapshot']
        item.update(online=state['online'], seen_at=state['seen_at'],
            enabled=state.get('enabled', True), controller_session_id=state.get('controller_session_id'),
            server_time=state['server_time'],
            offline_after_ms=state.get('offline_after_ms', int(OFFLINE_SECONDS * 1000)),
            heartbeat_age_ms=state.get('heartbeat_age_ms'),
            received_at=snapshot.get('received_at') if snapshot else None,
            generation=snapshot.get('generation') if snapshot else None,
            reported_on=output_value(snapshot, item['output']) if snapshot else None,
            elapsed_ms=reported_elapsed(snapshot, item['output']) if snapshot else None)
    return {'equipment': result}
