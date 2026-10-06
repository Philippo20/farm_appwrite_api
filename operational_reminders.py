"""Persist missed deadlines and farm alerts for every client's shared inbox."""
import json
import logging
from datetime import date, datetime, timezone
from device_maintenance import plans_for, schedule_view
from workflow_notifications import ADMIN_ROLES, publish_event


def maintenance_events(devices, history, today):
    for device in devices:
        if device.get('status') == 'Inactive': continue
        records = [row for row in history if row.get('device_id') == device['$id']]
        for plan in plans_for(device):
            task = schedule_view(device, plan, records, today)
            due = date.fromisoformat(task['due_date'])
            days = (due - today).days
            if days > 7: continue
            state = 'overdue' if days < 0 else 'due today' if days == 0 else 'due soon'
            yield f"maintenance:{device['$id']}:{plan['id']}:{due}:{state}", {
                'title': f"Maintenance {state}", 'kind': 'maintenance',
                'message': f"{task['device_name']} ({task['serial_number']}): {task['type']} on {task['farm_name']} is due {due}.",
                'recipients': {plan.get('assigned_to_id')}, 'roles': ADMIN_ROLES,
                'priority': 'high' if days <= 0 else 'normal',
            }


def publish_operational_reminders():
    from db import db
    from main import db_id, db_collection_id11, db_collection_id12, db_collection_id23
    from document_paging import list_all_documents
    from routes.device_maintenance import HISTORY
    def rows(collection):
        return list_all_documents(db, database_id=db_id, collection_id=collection)['documents']
    today = datetime.now(timezone.utc).date()
    # Isolate categories so a missing legacy collection cannot stop other alerts.
    def maintenance():
        devices = rows(db_collection_id11)
        history = [json.loads(row['payload']) for row in rows(HISTORY)]
        for key, event in maintenance_events(devices, history, today):
            publish_event(key, event)
    def tasks():
        for task in rows(db_collection_id23):
            if str(task.get('status', '')).lower() in {'completed', 'cancelled', 'canceled'}: continue
            raw = task.get('due_date')
            if not raw: continue
            due = date.fromisoformat(raw[:10])
            if due > today: continue
            state = 'overdue' if due < today else 'due today'
            publish_event(f"task:{task['$id']}:{due}:{state}", {
                'title': f'Task {state}', 'kind': 'task', 'priority': 'high',
                'message': f"{task.get('title', 'Farm task')} on {task.get('farm_name', 'your farm')} is due {due}.",
                'recipients': {task.get('assigned_to_id'), task.get('assigned_by_id')},
            })
    def alerts():
        for alert in rows(db_collection_id12):
            if alert.get('resolved'): continue
            publish_event(f"alert:{alert['$id']}", {
                'title': 'Farm alert', 'kind': 'issue', 'priority': 'high' if alert.get('severity') == 'high' else 'normal',
                'message': str(alert.get('message') or 'A farm alert needs attention.'),
                'roles': ADMIN_ROLES, 'farm': alert.get('farmID'),
            })
    for category in (maintenance, tasks, alerts):
        try: category()
        except Exception:
            logging.getLogger(__name__).exception('%s reminder pass failed', category.__name__)
