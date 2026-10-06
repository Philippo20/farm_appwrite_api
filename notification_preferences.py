from user_roles import has_role
"""Delivery preferences never remove items from the user's persistent inbox."""
import logging


def preferences_for(actor):
    if not has_role(actor, 'caretaker'): return {}
    try:
        from db import db
        from main import db_id, db_collection_id27
        from appwrite.query import Query
        rows = db.list_documents(database_id=db_id, collection_id=db_collection_id27,
            queries=[Query.equal('user_id', [actor['$id']]), Query.limit(1)])['documents']
        return rows[0] if rows else {}
    except Exception:
        logging.getLogger(__name__).warning('Unable to load notification delivery preferences')
        return {'delivery_unavailable': True}


def delivery_options(kind, preferences):
    key = {'message': 'chat_notifications', 'task': 'task_reminders',
           'maintenance': 'task_reminders', 'batch': 'task_reminders',
           'harvest': 'task_reminders', 'issue': 'anomaly_alerts', 'sensor_alert': 'anomaly_alerts'}.get(kind)
    return {'delivery_enabled': not preferences.get('delivery_unavailable', False)
            and (not key or preferences.get(key, True) is not False),
            'silent': preferences.get('sound_alerts', True) is False}
