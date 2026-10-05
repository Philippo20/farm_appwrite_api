"""Device maintenance policy; schedules are independent of telemetry state."""
import hashlib
import json
from datetime import date, timedelta

TASK_TYPES = {'cleaning', 'calibration', 'servicing', 'inspection'}


def plans_for(device):
    raw = device.get('maintenance_plan')
    if not raw:
        return []
    plans = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(plans, list):
        raise ValueError('Invalid stored device maintenance plan')
    return plans


def can_manage(profile, farm):
    if str(profile.get('status', '')).lower() != 'active':
        return False
    role = str(profile.get('role', '')).lower()
    if role in {'admin', 'superadmin'}:
        return True
    identities = {str(profile.get('$id') or ''), str(profile.get('email') or '')} - {''}
    assigned = profile.get('assignedFarmIds') or profile.get('assigned_farm_ids') or profile.get('assigned_farms') or []
    if not isinstance(assigned, list): assigned = []
    return role == 'technician' and (str(farm.get('$id')) in {str(value) for value in assigned} or str(farm.get('technician_id') or '') in identities
        or str(profile.get('farmID') or '') == str(farm.get('$id') or 'missing'))


def occurrence_id(device_id, plan_id, due):
    return hashlib.sha256(f'{device_id}:{plan_id}:{due}'.encode()).hexdigest()[:36]


def schedule_view(device, plan, history, today=None):
    today = today or date.today()
    completed = [row for row in history if row.get('plan_id') == plan['id']]
    latest = max(completed, key=lambda row: row['completed_on'], default=None)
    due = (date.fromisoformat(latest['completed_on']) + timedelta(days=plan['interval_days'])
           if latest else date.fromisoformat(plan['first_due']))
    status = 'Overdue' if due < today else 'Due soon' if due <= today + timedelta(days=7) else 'Scheduled'
    return {'device_id': device['$id'], 'plan_id': plan['id'], 'type': plan['type'],
            'device_name': device.get('model_number') or device.get('sensortype'),
            'serial_number': device.get('serial_number', ''), 'farm_id': device['farmID'],
            'farm_name': device.get('farm_name', ''), 'due_date': due.isoformat(),
            'interval_days': plan['interval_days'], 'instructions': plan.get('instructions', ''),
            'assigned_to_id': plan.get('assigned_to_id', ''), 'status': status,
            'last_completed_on': latest['completed_on'] if latest else None}
