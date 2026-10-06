from farm_assignments import is_farm_caretaker
"""Authenticated calendar and financial review backed by existing collections."""
from datetime import datetime, timezone
from typing import Literal

from appwrite.exception import AppwriteException
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from audit_utils import write_audit
from db import db
from document_paging import list_all_documents
from main import db_id, db_collection_id2, db_collection_id5, db_collection_id10, db_collection_id22, db_collection_id23
from production_planning import schedule
from routes.messaging import current_member

router = APIRouter(tags=['Live workspace'])


def _rows(collection):
    return list_all_documents(db, database_id=db_id, collection_id=collection)['documents']


def _role(actor):
    return str(actor.get('role', '')).lower().replace(' ', '_')


def _finance_access(actor):
    if _role(actor) not in {'accountant', 'admin', 'superadmin', 'super_admin'}:
        raise HTTPException(403, 'Financial review access is required.')


@router.get('/caretaker/calendar')
def calendar(actor=Depends(current_member)):
    if _role(actor) != 'caretaker':
        raise HTTPException(403, 'Caretaker access is required.')
    farms = {f['$id']: f for f in _rows(db_collection_id2) if is_farm_caretaker(f, actor)}
    events = []
    for task in _rows(db_collection_id23):
        # Include directly assigned tasks, and unassigned farm-wide tasks only.
        assignee = str(task.get('assigned_to_id') or '').strip()
        if assignee != actor['$id'] and not (task.get('farm_id') in farms and assignee.lower() in {'', 'unassigned'}):
            continue
        if not task.get('due_date'):
            continue
        events.append({'id': 'task:' + task['$id'], 'title': task.get('title', 'Farm task'),
                       'date': task['due_date'], 'type': 'task', 'status': task.get('status', 'Pending'),
                       'farm_name': task.get('farm_name', ''), 'description': task.get('description', ''),
                       'comment': task.get('manager_comment', '')})
    for batch in _rows(db_collection_id5):
        if batch.get('farmID') not in farms or str(batch.get('production_status', '')).lower() in {'harvested', 'delivered', 'completed', 'cancelled'}:
            continue
        try:
            plan = schedule(batch.get('production_plan'), batch.get('start_date'))
        except (ValueError, TypeError, KeyError):
            plan = {}
        dates = [(s['start_date'], s['name'], 'stage') for s in plan.get('stages', [])]
        harvest = plan.get('expected_harvest') or batch.get('end_date')
        if harvest:
            dates.append((harvest, 'Expected harvest', 'harvest'))
        for index, (due, title, kind) in enumerate(dates):
            events.append({'id': f"batch:{batch['$id']}:{index}", 'title': title, 'date': due,
                           'type': kind, 'status': batch.get('production_status', ''),
                           'farm_name': farms[batch['farmID']].get('name', ''),
                           'description': 'Batch ' + str(batch.get('batch_no') or batch['$id']), 'comment': ''})
    events.sort(key=lambda event: (event['date'], event['id']))
    return {'users': events, 'count': len(events)}


def _approval(row, kind):
    funds = kind == 'fund_request'
    return {'id': row['$id'], 'kind': kind,
            'reference': row.get('request_id' if funds else 'transaction_id') or row['$id'],
            'title': row.get('purpose') if funds else 'Withdrawal request',
            'requester': row.get('requested_by_name' if funds else 'user_name', ''),
            'requester_id': row.get('requested_by_id' if funds else 'user_id', ''),
            'farm_name': row.get('farm_name', ''), 'amount': row.get('amount', 0),
            'currency': row.get('currency', 'GHS'),
            'status': row.get('status' if funds else 'withdrawal_status', 'Pending'),
            'description': row.get('description' if funds else 'note', ''),
            'category': row.get('category', 'Withdrawal'), 'priority': row.get('priority', ''),
            'requested_at': row.get('request_date' if funds else 'requested_at', row.get('$createdAt', '')),
            'decision_notes': row.get('decision_notes', ''),
            'reviewer': row.get('approved_by_name', ''),
            'reviewed_at': row.get('approved_at' if funds else 'processed_at', ''),
            'revision': row.get('$updatedAt', '')}


@router.get('/accountant/approvals')
def approvals(actor=Depends(current_member)):
    _finance_access(actor)
    rows = [_approval(r, 'fund_request') for r in _rows(db_collection_id22)]
    rows += [_approval(r, 'withdrawal') for r in _rows(db_collection_id10) if r.get('transaction_type') == 'Withdrawal']
    rows.sort(key=lambda row: (row['status'] != 'Pending', row['requested_at'], row['id']))
    return {'users': rows, 'count': len(rows)}


class Decision(BaseModel):
    decision: Literal['Approved', 'Rejected']
    notes: str = Field(default='', max_length=1000)
    revision: str = Field(min_length=1, max_length=100)


@router.patch('/accountant/approvals/{kind}/{document_id}')
def review(kind: Literal['fund_request', 'withdrawal'], document_id: str, payload: Decision,
           actor=Depends(current_member)):
    _finance_access(actor)
    collection = db_collection_id22 if kind == 'fund_request' else db_collection_id10
    try:
        previous = db.get_document(database_id=db_id, collection_id=collection, document_id=document_id)
    except AppwriteException as error:
        if error.code == 404:
            raise HTTPException(404, 'Request not found.') from error
        raise
    if kind == 'withdrawal' and previous.get('transaction_type') != 'Withdrawal':
        raise HTTPException(404, 'Withdrawal request not found.')
    owner = previous.get('requested_by_id' if kind == 'fund_request' else 'user_id')
    if owner == actor['$id']:
        raise HTTPException(403, 'Another reviewer must review your own request.')
    key = 'status' if kind == 'fund_request' else 'withdrawal_status'
    if previous.get(key) != 'Pending' or previous.get('$updatedAt') != payload.revision:
        raise HTTPException(409, 'This request has changed. Refresh before reviewing it.')
    if payload.decision == 'Rejected' and not payload.notes.strip():
        raise HTTPException(422, 'Explain why this request is rejected.')
    now = datetime.now(timezone.utc).isoformat()
    data = {key: payload.decision, 'decision_notes': payload.notes.strip()}
    if kind == 'fund_request':
        data.update(approved_by_id=actor['$id'], approved_by_name=actor.get('name', ''), approved_at=now, updated_at=now)
    else:
        data['processed_at'] = now
    saved = db.update_document(database_id=db_id, collection_id=collection, document_id=document_id, data=data)
    write_audit(action_type='Update', collection_name='Fund Requests' if kind == 'fund_request' else 'Wallet',
                performed_by_id=actor['$id'], performed_by_role=_role(actor),
                action_details=f"{payload.decision} {kind} {document_id} by {actor.get('name', '')}",
                previous_data=previous, new_data={**previous, **data})
    return {'request': _approval(saved, kind)}
