from user_roles import assigned_roles
"""Explicit business-event policy, separate from delivery and email preferences."""
import hashlib
import logging
from datetime import datetime, timezone

ADMIN_ROLES = {'admin', 'superadmin', 'super_admin'}
FARM_ASSIGNMENTS = ('ownerID', 'caretakerID', 'farm_manager_id', 'technician_id')


def sensor_band(sensor):
    import math
    try:
        value = float(sensor['value'])
        if not math.isfinite(value): return None
        low, high = sensor.get('range_min'), sensor.get('range_max')
        if low is None and high is None: return None
        if low is not None and value < float(low): return 'below range'
        if high is not None and value > float(high): return 'above range'
        return 'normal'
    except (ValueError, TypeError, KeyError):
        return None


def events_for(collection, action, previous, current):
    """No telemetry noise or generic CRUD broadcasts. Return only actionable events."""
    if action not in {'Create', 'Update'}:
        return []
    old = previous or {}
    data = {**old, **(current or {})}
    events = []

    def event(title, message, kind='system', recipients=(), roles=(), farm='', priority='normal'):
        events.append(dict(title=title, message=message, kind=kind,
                           recipients=set(recipients) - {'', None, 'Unassigned'},
                           roles=set(roles), farm=farm, priority=priority))

    if collection == 'Sensor readings':
        band = sensor_band(data)
        previous_band = sensor_band(old)
        if data.get('alerts_enabled') is True and band and band != previous_band:
            if band != 'normal' or previous_band in {'below range', 'above range'}:
                event('Sensor recovered' if band == 'normal' else 'Sensor outside safe range',
                      f"{data.get('serial_number', 'Sensor')} on {data.get('farm_name', 'your farm')}: {band}.",
                      'sensor_alert', roles=ADMIN_ROLES, farm=data.get('farmID', ''),
                      priority='normal' if band == 'normal' else 'high')
    elif collection == 'Device maintenance':
        from device_maintenance import plans_for
        previous_plans = {plan['id']: plan for plan in plans_for(old)}
        for plan in plans_for(data):
            if plan != previous_plans.get(plan['id']):
                event('Maintenance assignment', f"{data.get('model_number', 'Device')}: {plan['type']} plan assigned or updated. Check the maintenance schedule.",
                      'maintenance', recipients=[plan.get('assigned_to_id')])
    elif collection == 'Maintenance completion':
        event('Maintenance completed', f"{data.get('device_name', 'Device')}: {data.get('type', 'maintenance')} completed on {data.get('completed_on', '')}.",
              'maintenance', roles=ADMIN_ROLES, farm=data.get('farm_id', ''))
    elif collection == 'Farm Records' and data.get('has_issues') and action == 'Create':
        event('Farm issue reported', f"An issue was recorded on {data.get('farm_name', 'a farm')}. Review the caretaker record.",
              'issue', roles=ADMIN_ROLES, farm=data.get('farm_id', ''),
              priority='urgent' if data.get('issue_severity') == 'critical' else
                       'high' if data.get('issue_severity') == 'high' else 'normal')
    elif collection == 'Backups' and (action == 'Create' or 'replace_collections' in data):
        event('Backup completed' if action == 'Create' else 'Restore completed',
              'A system backup completed.' if action == 'Create' else 'A system restore completed. Review the audit log.',
              roles={'superadmin'})
    elif collection == 'Fund Requests':
        state = data.get('status')
        if state != old.get('status'):
            if action == 'Create':
                event('Fund request awaiting review', f"A new fund request for {data.get('farm_name', 'a farm')} needs review.",
                      'fund_request', roles=ADMIN_ROLES | {'accountant'}, priority='high')
            else:
                event('Fund request updated', f"Request {data.get('request_id', '')} is now {state}.",
                      'fund_request', recipients=[data.get('requested_by_id')])
    elif collection == 'Wallet' and data.get('transaction_type') == 'Withdrawal':
        state = data.get('withdrawal_status')
        if state != old.get('withdrawal_status'):
            event('Withdrawal request' if action == 'Create' else 'Withdrawal updated',
                  f"Withdrawal {data.get('transaction_id', '')} is {state}.", 'withdrawal',
                  recipients=[data.get('user_id')],
                  roles=ADMIN_ROLES | {'accountant'} if action == 'Create' else ())
    elif collection == 'Farms':
        for field in FARM_ASSIGNMENTS:
            assigned = data.get(field)
            if assigned and assigned != old.get(field):
                event('Farm assignment', f"You have been assigned to {data.get('name', 'a farm')}.", recipients=[assigned])
    elif collection == 'Users':
        if action == 'Create':
            event('New user account', 'A new user account has been created. Review its approval and farm assignments.', 'account_review', roles=ADMIN_ROLES)
        elif any(data.get(field) != old.get(field) for field in ('status', 'role')):
            event('Account updated', 'Your account role or approval status has changed.', recipients=[data.get('$id')])
    elif collection == 'Batches':
        changed = [field for field in ('production_status', 'delivery_status') if data.get(field) != old.get(field)]
        if action == 'Create' or changed:
            details = ', '.join(str(data[field]) for field in changed if data.get(field))
            event('Batch created' if action == 'Create' else 'Batch updated',
                  f"Batch {data.get('batch_no', '')}: {details or 'ready for tracking'}.",
                  'batch', farm=data.get('farmID', ''))
    elif collection == 'Inventory':
        def stock_state(item):
            if item.get('status') == 'Expired': return 'expired'
            if 'quantity_available' not in item: return ''
            quantity = float(item.get('quantity_available') or 0)
            return 'out of stock' if quantity <= 0 else 'low stock' if quantity <= float(item.get('reorder_level') or 0) else 'available'
        state = stock_state(data)
        if state not in ('', 'available') and state != stock_state(old):
            event('Inventory needs attention', f"{data.get('item_name', 'An inventory item')} is {state}.",
                  'inventory_alert', roles=ADMIN_ROLES, farm=data.get('farm_id', ''), priority='high')
    return events


def publish_event(key, event):
    """Recipient-scoped, idempotent persistence; no additional email is sent."""
    from appwrite.exception import AppwriteException
    from db import db
    from main import db_id, db_collection_id1, db_collection_id2, db_collection_id25
    from document_paging import list_all_documents
    users = list_all_documents(db, database_id=db_id, collection_id=db_collection_id1)['documents']
    recipients = set(event.get('recipients', ()))
    farm_id = event.get('farm')
    if farm_id:
        try:
            farm = db.get_document(db_id, db_collection_id2, farm_id)
            recipients.update(farm.get(field) for field in FARM_ASSIGNMENTS)
        except AppwriteException as error:
            if error.code != 404: raise
    roles = event.get('roles', ())
    recipients.difference_update({'', None, 'Unassigned'})
    for user in users:
        if str(user.get('status', '')).lower() != 'active': continue
        if user['$id'] not in recipients and user.get('email') not in recipients and not set(assigned_roles(user)).intersection(roles):
            continue
        identifier = hashlib.sha256(f"{key}:{user['$id']}".encode()).hexdigest()[:36]
        try:
            db.create_document(database_id=db_id, collection_id=db_collection_id25,
                document_id=identifier, data={
                    'notification_id': identifier, 'recipient_id': user['$id'],
                    'recipient_name': user.get('name', ''), 'title': event['title'][:225],
                    'message': event['message'][:2000], 'type': event.get('kind', 'system'),
                    'priority': event.get('priority', 'normal'), 'is_read': False,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                })
        except AppwriteException as error:
            if error.code != 409: raise
        else:
            from push_notifications import queue_push
            queue_push(user['$id'], event.get('kind', 'system'), identifier)


def notify_change(collection, action, previous=None, current=None):
    """A failed notification must never make an already-saved action look failed."""
    try:
        old, new = previous or {}, current or {}
        data = {**old, **new}
        identity = next((data.get(k) for k in ('$id', 'request_id', 'transaction_id', 'item_id', 'batch_no', 'record_id', 'backup_id') if data.get(k)), data.get('name', ''))
        # The previous revision distinguishes a later repeat of a valid transition.
        revision = old.get('$updatedAt', '')
        for index, event in enumerate(events_for(collection, action, old, new)):
            key = f"workflow:{collection}:{identity}:{revision}:{index}:{event['message']}"
            publish_event(key, event)
    except Exception:
        logging.getLogger(__name__).exception('Workflow notification failed for %s', collection)
