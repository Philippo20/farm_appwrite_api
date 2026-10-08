"""Growing group membership and one-event, many-batch caretaker records."""
import json
import uuid
from fastapi import HTTPException
from appwrite.query import Query
from production_planning import record_growth_plan, growth_stage_at

SHARED_TYPES = {'daily_monitoring', 'watering', 'feeding', 'pruning', 'pest_control'}


def can_manage_group(actor, farm):
    role = str(actor.get('role', '')).lower().replace(' ', '_')
    if role in {'admin', 'superadmin', 'super_admin'}:
        return True
    identities = {actor.get('$id'), actor.get('email')} - {None, ''}
    return role == 'farm_manager' and farm.get('farm_manager_id') in identities


def group_assignment(identity, name, farm, actor, find_members, previous=None):
    if identity is None:
        return {}
    if not can_manage_group(actor, farm):
        raise HTTPException(403, 'Only administrators or the assigned farm manager can link batches.')
    identity, name = identity.strip(), (name or '').strip()
    if previous and any(str(previous.get(k, '')).lower() in {'complete', 'completed', 'delivered'}
                        for k in ('production_status', 'delivery_status')):
        raise HTTPException(409, 'Completed batches cannot change growing group.')
    if identity == 'individual':
        identity = ''
    if not identity:
        return {'growing_group_id': '', 'growing_group_name': ''}
    if identity == 'new':
        if not name or len(name) > 100:
            raise HTTPException(422, 'Enter a growing group name of 1–100 characters.')
        identity = uuid.uuid4().hex
    else:
        members = find_members(identity)
        if not members or any(b.get('farmID') != farm['$id'] for b in members):
            raise HTTPException(422, 'Choose a growing group belonging to this farm.')
        name = members[0].get('growing_group_name', '')
    return {'growing_group_id': identity, 'growing_group_name': name}


def linked_entries(raw, farm_id, primary_id, record_type, record_date, load_batch, load_plant, ensure_open):
    try:
        entries = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Linked batch details must be a JSON list.') from None
    if not isinstance(entries, list) or not 2 <= len(entries) <= 20:
        raise HTTPException(422, 'Select 2–20 batches for a shared record.')
    if record_type not in SHARED_TYPES:
        raise HTTPException(422, 'Record planting and harvest totals individually for each batch.')
    result, seen, group = [], set(), None
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('batch_id'), str):
            raise HTTPException(422, 'Every linked entry must identify a batch.')
        identity = entry['batch_id']
        if identity in seen:
            raise HTTPException(422, 'A batch cannot appear twice in a shared record.')
        seen.add(identity)
        try:
            batch = load_batch(identity)
        except Exception:
            raise HTTPException(404, 'A selected linked batch no longer exists.') from None
        if batch.get('farmID') != farm_id or not batch.get('growing_group_id'):
            raise HTTPException(403, 'All selected batches must belong to the same farm and growing group.')
        group = group or batch['growing_group_id']
        if batch['growing_group_id'] != group:
            raise HTTPException(422, 'The selected batches are no longer in the same growing group. Refresh and retry.')
        ensure_open(batch)
        fields = {}
        for key, maximum in [('observations', 2000), ('plant_health', 200), ('issue_description', 2000)]:
            value = entry.get(key, '')
            if not isinstance(value, str) or len(value) > maximum:
                raise HTTPException(422, f'{key.replace("_", " ")} must be text within {maximum} characters.')
            fields[key] = value.strip()
        issues = entry.get('has_issues', False)
        if not isinstance(issues, bool):
            raise HTTPException(422, 'Choose whether each batch has an issue.')
        severity = entry.get('issue_severity', 'none') if issues else 'none'
        if severity not in {'none', 'low', 'medium', 'high', 'critical'} or (issues and (severity == 'none' or not fields['issue_description'])):
            raise HTTPException(422, 'Describe the issue and select its severity for each affected batch.')
        if not issues:
            fields['issue_description'] = ''
        try:
            stage = growth_stage_at(record_growth_plan(batch, load_plant), batch.get('start_date'), record_date)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except Exception as error:
            raise HTTPException(503, 'Unable to load a linked batch growth plan. Please retry.') from error
        result.append({**fields, 'batch_id': identity, 'batch_number': batch.get('batch_no', identity),
                       'growth_stage': stage, 'has_issues': issues, 'issue_severity': severity})
    if primary_id not in seen:
        raise HTTPException(422, 'The selected batch must be included in the shared record.')
    if len(json.dumps(result, ensure_ascii=False)) > 60000:
        raise HTTPException(422, 'Linked observations are too long. Shorten them or record fewer batches together.')
    return group, result


def batch_record_view(record, batch_id):
    """Project one event into the selected batch log without duplicating storage."""
    if not record.get('batch_entries'):
        return record
    entries = json.loads(record['batch_entries'])
    entry = next((e for e in entries if e['batch_id'] == batch_id), None)
    if entry is None:
        return record
    return {**record, **entry, 'shared_observations': record.get('observations', ''),
            'record_scope': 'shared', 'linked_batches': entries}


def batch_record_query(batch_id):
    return Query.or_queries([Query.equal('batch_id', [batch_id]), Query.contains('linked_batch_ids', [batch_id])])
