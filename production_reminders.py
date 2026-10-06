"""Persisted in-app reminders; deterministic IDs make multiple API workers safe."""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from production_planning import reminder_events


def publish_reminders():
    from db import db
    from main import db_id, db_collection_id1, db_collection_id2, db_collection_id5, db_collection_id25
    from document_paging import list_all_documents
    from appwrite.exception import AppwriteException
    def rows(collection):
        return list_all_documents(db, database_id=db_id, collection_id=collection)['documents']
    batches = rows(db_collection_id5)
    if not any(b.get('production_plan') for b in batches):
        return
    farms = {f['$id']: f for f in rows(db_collection_id2)}
    users = {u['$id']: u for u in rows(db_collection_id1)
             if str(u.get('status', '')).lower() == 'active'}
    admins = {key for key, u in users.items() if str(u.get('role', '')).lower() in ('admin', 'superadmin', 'super_admin')}
    now = datetime.now(timezone.utc)
    for batch, kind, due, title, state in reminder_events(batches, now.date()):
        farm = farms.get(batch['farmID'])
        if not farm:
            continue
        recipients = admins | {farm.get('caretakerID'), farm.get('farm_manager_id')}
        for recipient in recipients & users.keys():
            key = f"{batch['$id']}:{kind}:{due}:{state}:{recipient}"
            identifier = hashlib.sha256(key.encode()).hexdigest()[:36]
            message = (f"{batch.get('farm_name', '')} · {batch.get('plant_name', '')} · "
                       f"Batch {batch.get('batch_no', '')}: {title} on {due} ({state}). "
                       'Dates are planned; record actual progress separately.')
            try:
                db.create_document(database_id=db_id, collection_id=db_collection_id25,
                    document_id=identifier, data={
                        'notification_id': identifier, 'recipient_id': recipient,
                        'recipient_name': users[recipient].get('name', ''),
                        'title': title, 'message': message, 'type': 'harvest' if kind == 'harvest' else 'batch',
                        'priority': 'high' if state == 'overdue' else 'normal',
                        'is_read': False, 'created_at': now.isoformat(),
                        'related_task_id': batch['$id'],
                    })
            except AppwriteException as error:
                if error.code != 409:
                    raise
            else:
                from push_notifications import queue_push
                queue_push(recipient, 'harvest' if kind == 'harvest' else 'batch', identifier)


async def reminder_loop():
    while True:
        try:
            await asyncio.to_thread(publish_reminders)
        except Exception:
            logging.getLogger(__name__).exception('Production reminder pass failed; retrying in five minutes')
        try:
            from operational_reminders import publish_operational_reminders
            await asyncio.to_thread(publish_operational_reminders)
        except Exception:
            logging.getLogger(__name__).exception('Operational reminders failed; retrying in five minutes')
        await asyncio.sleep(300)


@asynccontextmanager
async def production_lifespan(app):
    task = asyncio.create_task(reminder_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
