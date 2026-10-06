from user_roles import effective_profile, has_role
"""Authenticated device registration, independent schedules and append-only history."""
import json
import math
import os
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from appwrite.query import Query
from appwrite.exception import AppwriteException
from appwrite.id import ID
from auth import get_current_user
from db import db
from main import db_id, db_collection_id1, db_collection_id2, db_collection_id11
from device_maintenance import can_manage, plans_for, schedule_view, occurrence_id

router = APIRouter(prefix='/device-maintenance', tags=['Device maintenance'])
HISTORY = os.getenv('APPWRITE_DEVICE_MAINTENANCE_HISTORY', 'device_maintenance_history')


def actor_profile(actor=Depends(get_current_user)):
    profiles = db.list_documents(db_id, db_collection_id1,
        queries=[Query.equal('email', [actor.get('email', '')]), Query.limit(2)])['documents']
    if len(profiles) == 1:
        profiles[0] = effective_profile(profiles[0], actor.get('_active_role'))
    if len(profiles) != 1 or profiles[0].get('status') != 'Active' or profiles[0].get('role') not in {'admin', 'superadmin', 'technician'}:
        raise HTTPException(403, 'Only active administrators and assigned technicians can manage devices.')
    return profiles[0]


def rows(collection, queries=None):
    result, offset = [], 0
    while True:
        page = db.list_documents(db_id, collection, queries=[*(queries or []), Query.order_asc('$id'), Query.limit(100), Query.offset(offset)])['documents']
        result.extend(page)
        if len(page) < 100: return result
        offset += len(page)


def authorized_farm(profile, farm_id):
    farm = db.get_document(db_id, db_collection_id2, farm_id)
    if not can_manage(profile, farm):
        raise HTTPException(403, 'This farm is not assigned to you.')
    return farm


def device_for(profile, device_id):
    device = db.get_document(db_id, db_collection_id11, device_id)
    farm = authorized_farm(profile, device['farmID'])
    return device, farm


class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default='', max_length=36, pattern=r'^[a-zA-Z0-9-]*$')
    type: Literal['cleaning', 'calibration', 'servicing', 'inspection']
    interval_days: int = Field(ge=1, le=3650)
    first_due: date
    assigned_to_id: str = Field(default='', max_length=64)
    instructions: str = Field(default='', max_length=1000)


class Device(BaseModel):
    model_config = ConfigDict(extra='forbid')
    farmID: str = Field(min_length=1, max_length=64)
    sensortype: str = Field(min_length=1, max_length=64)
    model_number: str = Field(min_length=1, max_length=225)
    serial_number: str = Field(default='', max_length=225)
    location: str = Field(min_length=1, max_length=225)
    value: float = 0
    unit: str = Field(default='', max_length=225)
    status: Literal['Active', 'Inactive', 'Faulty', 'Maintenance'] = 'Active'
    alerts_enabled: bool = True
    range_min: float | None = None
    range_max: float | None = None
    warning_min: float | None = None
    warning_max: float | None = None
    plans: list[Plan] = Field(default_factory=list, max_length=4)


def prepare_plans(submitted, previous, profile, farm):
    old = {plan['id']: plan for plan in plans_for(previous or {})}
    result, types = [], set()
    for plan in submitted:
        if plan.type in types:
            raise HTTPException(422, 'Choose each maintenance type only once.')
        types.add(plan.type)
        if plan.id and (plan.id not in old or old[plan.id]['type'] != plan.type):
            raise HTTPException(422, 'Maintenance plan changed. Reload this device.')
        data = plan.model_dump(mode='json')
        data['id'] = plan.id or str(uuid4())
        assigned = plan.assigned_to_id or str(farm.get('technician_id') or '')
        if assigned == 'Unassigned': assigned = ''
        if assigned:
            try:
                assignee = db.get_document(db_id, db_collection_id1, assigned)
            except AppwriteException as error:
                if error.code != 404: raise
                raise HTTPException(422, 'Assign an active technician to this farm first.') from error
            if not has_role(assignee, 'technician') or not can_manage({**assignee, 'role': 'technician'}, farm):
                raise HTTPException(422, 'Maintenance must be assigned to an active technician for this farm.')
        data['assigned_to_id'] = assigned
        result.append(data)
    return result


def save_device(body, profile, device_id=None):
    from routes.r11_sensors import SensorType, _sensor_document_payload, _next_sensor_serial_number
    previous = device_for(profile, device_id)[0] if device_id else None
    farm = authorized_farm(profile, body.farmID)
    if previous and previous['farmID'] != body.farmID:
        raise HTTPException(422, 'Keep this device on its registered farm to preserve its maintenance history.')
    if body.sensortype not in {kind.value for kind in SensorType}:
        raise HTTPException(422, 'Choose a supported device type.')
    for value in (body.value, body.range_min, body.range_max, body.warning_min, body.warning_max):
        if value is not None and not math.isfinite(value):
            raise HTTPException(422, 'Readings and limits must be finite numbers.')
    for low, high in ((body.range_min, body.range_max), (body.warning_min, body.warning_max)):
        if low is not None and high is not None and low > high:
            raise HTTPException(422, 'The low limit must not exceed the high limit.')
    if not body.model_number.strip() or not body.location.strip():
        raise HTTPException(422, 'Device name and location are required.')
    plans = prepare_plans(body.plans, previous, profile, farm)
    serial = body.serial_number.strip() or (previous or {}).get('serial_number') or _next_sensor_serial_number(body.farmID, farm['name'])
    duplicates = rows(db_collection_id11, [Query.equal('serial_number', [serial])])
    if any(item['$id'] != device_id for item in duplicates):
        raise HTTPException(409, 'This device serial number is already registered.')
    data = _sensor_document_payload(farmID=body.farmID, farm_name=farm['name'], sensortype=body.sensortype,
        model_number=body.model_number.strip(), serial_number=serial, location=body.location.strip(),
        value=body.value, status_value=body.status, unit=body.unit, alerts_enabled=body.alerts_enabled,
        maintenance_frequency='Per task' if plans else 'Not required',
        timestamp=(previous or {}).get('timestamp') or datetime.now(timezone.utc).isoformat(),
        last_maintenance_date=(previous or {}).get('last_maintenance_date'),
        range_min=body.range_min, range_max=body.range_max, warning_min=body.warning_min, warning_max=body.warning_max,
        maintenance_plan=plans)
    # Allow clearing a limit, while preserving telemetry and heartbeat on edits.
    for key in ('range_min', 'range_max', 'warning_min', 'warning_max'):
        data[key] = getattr(body, key)
    if previous:
        data.pop('value', None)
        saved = db.update_document(db_id, db_collection_id11, device_id, data)
    else:
        saved = db.create_document(db_id, db_collection_id11, ID.unique(), data, permissions=[])
    from workflow_notifications import notify_change
    notify_change('Device maintenance', 'Update' if previous else 'Create', previous, saved)
    return {'device': saved}


@router.get('/options')
def options(profile=Depends(actor_profile)):
    farms = [farm for farm in rows(db_collection_id2) if can_manage(profile, farm)]
    farm_ids = {farm['$id'] for farm in farms}
    devices = [device for device in rows(db_collection_id11) if device.get('farmID') in farm_ids]
    return {'farms': [{'$id': f['$id'], 'name': f['name'], 'technician_id': f.get('technician_id', '')} for f in farms],
            'devices': devices}


@router.post('/devices')
def create_device(body: Device, profile=Depends(actor_profile)):
    return save_device(body, profile)


@router.put('/devices/{device_id}')
def update_device(device_id: str, body: Device, profile=Depends(actor_profile)):
    return save_device(body, profile, device_id)


def history_for(device_id):
    return [{**json.loads(row['payload']), '$id': row['$id']} for row in rows(HISTORY, [Query.equal('device_id', [device_id])])]


@router.get('/overview')
def overview(profile=Depends(actor_profile)):
    available = options(profile)
    tasks = []
    farm_ids = {farm['$id'] for farm in available['farms']}
    # Completed records remain available even after a device is removed.
    history = [{**json.loads(row['payload']), '$id': row['$id']} for row in rows(HISTORY)
               if row.get('farm_id') in farm_ids]
    for device in available['devices']:
        records = [record for record in history if record.get('device_id') == device['$id']]
        for plan in plans_for(device):
            tasks.append(schedule_view(device, plan, records, datetime.now(timezone.utc).date()))
    names = {person['$id']: person.get('name', '') for person in rows(db_collection_id1)}
    for task in tasks:
        task['assigned_to_name'] = names.get(task.get('assigned_to_id'), 'Unassigned')
    tasks.sort(key=lambda task: (task['due_date'], task['serial_number'], task['type']))
    history.sort(key=lambda item: (item['completed_on'], item.get('recorded_at', '')), reverse=True)
    return {'tasks': tasks, 'history': history, **available}


class Completion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    due_date: date
    completed_on: date
    work_performed: str = Field(min_length=3, max_length=3000)
    calibration_results: str = Field(default='', max_length=2000)
    follow_up: str = Field(default='', max_length=2000)


@router.post('/devices/{device_id}/plans/{plan_id}/complete')
def complete(device_id: str, plan_id: str, body: Completion, profile=Depends(actor_profile)):
    device, farm = device_for(profile, device_id)
    plan = next((item for item in plans_for(device) if item['id'] == plan_id), None)
    if not plan:
        raise HTTPException(404, 'This maintenance task no longer exists. Reload the device.')
    if profile['role'] == 'technician' and plan.get('assigned_to_id') not in ('', None, profile['$id']):
        raise HTTPException(403, 'This task is assigned to another technician.')
    today = datetime.now(timezone.utc).date()
    records = history_for(device_id)
    current = schedule_view(device, plan, records, today)
    if body.due_date.isoformat() != current['due_date']:
        raise HTTPException(409, 'This task has already changed or been completed. Refresh the schedule.')
    last = current['last_completed_on']
    if body.completed_on > today or (last and body.completed_on <= date.fromisoformat(last)):
        raise HTTPException(422, 'Choose a completion date no later than today and after the previous completion.')
    if not body.work_performed.strip() or (plan['type'] == 'calibration' and not body.calibration_results.strip()):
        raise HTTPException(422, 'Describe the work and include calibration results for calibration tasks.')
    record = {**current, **body.model_dump(mode='json'), 'status': 'Completed',
        'performed_by_id': profile['$id'], 'performed_by_name': profile.get('name', ''),
        'recorded_at': datetime.now(timezone.utc).isoformat()}
    record_id = occurrence_id(device_id, plan_id, current['due_date'])
    try:
        db.create_document(db_id, HISTORY, record_id,
            {'device_id': device_id, 'farm_id': farm['$id'], 'payload': json.dumps(record)}, permissions=[])
    except AppwriteException as error:
        if error.code != 409: raise
        raise HTTPException(409, 'This occurrence has already been completed. Refresh the schedule.') from error
    from workflow_notifications import notify_change
    notify_change('Maintenance completion', 'Create', current={**record, '$id': record_id})
    return {'record': {**record, '$id': record_id},
            'next_task': schedule_view(device, plan, [*records, record], today)}
