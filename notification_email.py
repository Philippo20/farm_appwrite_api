"""Best-effort email companion to persisted in-app notifications."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from db import db
from main import db_id, db_collection_id18, db_collection_id1
from email_delivery import send_email

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='notification-email')
_slots = BoundedSemaphore(50)
_log = logging.getLogger(__name__)


def notification_category(kind):
    if kind in {'batch', 'farm', 'sensor', 'alert'}:
        return 'farm_alerts'
    if kind in {'account', 'security'}:
        return 'account_alerts'
    return 'workflow_alerts'


def _deliver(recipient_id, title, message, kind):
    try:
        global_config = db.get_document(database_id=db_id, collection_id=db_collection_id18, document_id='global')
        if not global_config.get('email_notifications', True):
            return
        document = db.get_document(database_id=db_id, collection_id=db_collection_id18, document_id='email')
        config = json.loads(document.get('email_settings_json') or '{}')
        category = notification_category(kind)
        if not config.get('enabled') or not config.get(category, True):
            return
        user = db.get_document(database_id=db_id, collection_id=db_collection_id1, document_id=recipient_id)
        if str(user.get('status', '')).lower() != 'active' or not user.get('email'):
            return
        send_email(config, user['email'], title, message, category)
    except Exception:
        # Do not log SMTP credentials, recipient details, or provider responses.
        _log.warning('Notification email could not be delivered; in-app notification retained')
    finally:
        _slots.release()


def queue_notification_email(recipient_id, title, message, kind):
    if not _slots.acquire(blocking=False):
        _log.warning('Notification email queue is full; in-app notification retained')
        return
    try:
        _pool.submit(_deliver, recipient_id, title, message, kind)
    except RuntimeError:
        _slots.release()
        _log.warning('Notification email worker unavailable; in-app notification retained')
