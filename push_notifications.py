"""Private, recipient-scoped Android delivery. Database inbox remains authoritative."""
import hashlib
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from appwrite.exception import AppwriteException
from appwrite.query import Query
from db import db
from document_paging import list_all_documents
from main import db_id, db_collection_id1
from notification_preferences import preferences_for, delivery_options

DEVICES = os.getenv('APPWRITE_PUSH_DEVICES_COLLECTION_ID', 'push_devices')
log = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='farm-push')
_slots = threading.BoundedSemaphore(256)


def enabled():
    return os.getenv('FCM_ENABLED', 'false').lower() == 'true'


def token_id(token):
    return hashlib.sha256(token.encode()).hexdigest()[:36]


@lru_cache(maxsize=1)
def firebase_app():
    import firebase_admin
    from firebase_admin import credentials
    # ADC reads GOOGLE_APPLICATION_CREDENTIALS; no private key is stored in code.
    raw = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON', '')
    credential = credentials.Certificate(json.loads(raw)) if raw else credentials.ApplicationDefault()
    return firebase_admin.initialize_app(credential,
        options={'projectId': os.getenv('FIREBASE_PROJECT_ID', 'farmestatesltd-f8616'), 'httpTimeout': 10}, name='farm-push')


def register(token, actor):
    data = {'token': token, 'recipient_id': actor['$id'], 'platform': 'android',
            'updated_at': datetime.now(timezone.utc).isoformat()}
    try:
        db.create_document(database_id=db_id, collection_id=DEVICES, document_id=token_id(token), data=data)
    except AppwriteException as error:
        if error.code != 409:
            raise
        # The authenticated installation can rebind its token after an account switch.
        db.update_document(database_id=db_id, collection_id=DEVICES, document_id=token_id(token), data=data)


def unregister(token, actor):
    try:
        device = db.get_document(database_id=db_id, collection_id=DEVICES, document_id=token_id(token))
        if device.get('recipient_id') == actor['$id']:
            db.delete_document(database_id=db_id, collection_id=DEVICES, document_id=device['$id'])
    except AppwriteException as error:
        if error.code != 404:
            raise


def queue_push(recipient, kind, event_id, peer=None):
    if not enabled():
        return
    if not _slots.acquire(blocking=False):
        log.warning('Push queue full; notification remains in the inbox')
        return
    def run():
        try:
            send_push(recipient, kind, event_id, peer)
        except Exception as error:
            # Do not log device tokens, credential contents, or SDK request payloads.
            log.warning('Push delivery failed (%s); notification remains in the inbox', type(error).__name__)
        finally:
            _slots.release()
    try:
        _pool.submit(run)
    except RuntimeError:
        _slots.release()
        log.warning('Push worker unavailable; notification remains in the inbox')


def send_push(recipient, kind, event_id, peer=None):
    from firebase_admin import messaging
    actor = db.get_document(database_id=db_id, collection_id=db_collection_id1, document_id=recipient)
    if str(actor.get('status', '')).lower() != 'active':
        return
    options = delivery_options(kind, preferences_for(actor))
    if not options['delivery_enabled']:
        return
    devices = list_all_documents(db, database_id=db_id, collection_id=DEVICES,
        queries=[Query.equal('recipient_id', [recipient])])['documents']
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for device in devices:
        if device.get('recipient_id') != recipient:
            continue
        try:
            updated = datetime.fromisoformat(device.get('updated_at', '').replace('Z', '+00:00'))
            if updated < cutoff:
                continue
        except (ValueError, TypeError):
            continue
        message = messaging.Message(token=device['token'], data={
            'recipientId': recipient, 'eventId': event_id,
            'peerId': peer or '__inbox__:' + event_id,
            'silent': str(options['silent']).lower(),
        }, android=messaging.AndroidConfig(priority='high', ttl=timedelta(hours=24)))
        try:
            messaging.send(message, app=firebase_app())
        except messaging.UnregisteredError:
            db.delete_document(database_id=db_id, collection_id=DEVICES, document_id=device['$id'])
        except Exception as error:
            log.warning('Push device delivery failed (%s)', type(error).__name__)
