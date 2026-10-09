"""Live due-work reminders scoped to the signed-in technician's farms."""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from appwrite.query import Query
from main import db_collection_id23
from device_maintenance import plans_for, schedule_view
from routes.device_maintenance import actor_profile, options, rows, HISTORY

router = APIRouter(prefix='/device-maintenance', tags=['Device maintenance'])


def due_item(item, today):
    if str(item.get('status', '')).lower() in {'completed', 'cancelled', 'canceled', 'closed', 'done'}:
        return None
    try:
        due = datetime.fromisoformat(str(item.get('due_date') or item.get('scheduled_date')).replace('Z', '+00:00')).date()
    except (TypeError, ValueError):
        return None
    if due > today:
        return None
    return {**item, 'due_date': due.isoformat(), 'overdue': due < today}


@router.get('/due-reminders')
def due_reminders(profile=Depends(actor_profile)):
    if profile.get('role') != 'technician':
        raise HTTPException(403, 'Technician access is required.')
    today = datetime.now(timezone.utc).date()
    available = options(profile)
    farms = {farm['$id'] for farm in available['farms']}
    if not farms:
        return {'items': [], 'count': 0, 'overdue_count': 0}
    history = [json.loads(row['payload']) for row in rows(HISTORY,
        [Query.equal('farm_id', sorted(farms))])]
    tasks = []
    for device in available['devices']:
        records = [record for record in history if record.get('device_id') == device['$id']]
        for plan in plans_for(device):
            if plan.get('assigned_to_id') not in ('', None, profile['$id']):
                continue
            item = schedule_view(device, plan, records, today)
            due = due_item(item, today)
            if due:
                tasks.append({**due, 'kind': 'device', 'title': f"{item['device_name']}: {item['type']}"})
    for task in rows(db_collection_id23, [Query.equal('farm_id', sorted(farms))]):
        if task.get('farm_id') not in farms:
            continue
        assigned = task.get('assigned_to_id') or task.get('technician_id')
        if assigned not in ('', None, profile['$id'], profile.get('email')):
            continue
        due = due_item(task, today)
        if due:
            tasks.append({**due, 'kind': 'farm_task'})
    tasks.sort(key=lambda item: (item['due_date'], str(item.get('title', ''))))
    return {'items': tasks, 'count': len(tasks),
            'overdue_count': sum(item['overdue'] for item in tasks)}
