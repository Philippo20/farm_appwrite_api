"""Current farm team membership, with compatibility for single-caretaker farms."""
import json
from fastapi import HTTPException
from user_roles import has_role


def caretaker_ids(farm):
    values = farm.get('caretaker_ids')
    if not isinstance(values, list) or not values:
        values = [farm.get('caretakerID') or farm.get('caretaker_id') or farm.get('caretakerId')]
    return list(dict.fromkeys(str(v).strip() for v in values
                             if v and str(v).strip().lower() not in {'', 'unassigned'}))


def is_farm_caretaker(farm, profile):
    identities = {str(profile.get(key) or '').strip().lower() for key in ('$id', 'id', 'email')} - {''}
    return bool(identities.intersection(v.lower() for v in caretaker_ids(farm)))


def requested_caretakers(raw, primary, previous=None):
    if raw is None:
        old = caretaker_ids(previous or {})
        old_primary = str((previous or {}).get('caretakerID') or 'Unassigned')
        if previous and primary == old_primary:
            return old
        values = [primary] + [v for v in old if v != old_primary]
    else:
        try: values = json.loads(raw)
        except (TypeError, ValueError): raise HTTPException(422, 'Select valid caretakers.') from None
        if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) or not v.strip() or v.lower() == 'unassigned' for v in values):
            raise HTTPException(422, 'Select valid caretakers.')
    return caretaker_ids({'caretaker_ids': values})


def validate_new_caretakers(ids, previous, load_user):
    for identity in set(ids) - set(caretaker_ids(previous or {})):
        try: user = load_user(identity)
        except Exception: raise HTTPException(422, 'A selected caretaker no longer exists.') from None
        if str(user.get('status', '')).lower() != 'active' or not has_role(user, 'caretaker'):
            raise HTTPException(422, 'Choose active users with the Caretaker role.')
