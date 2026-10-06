"""Role membership and per-request role selection. Never mutate a user's primary role on login."""
import json
from fastapi import HTTPException

ROLES = {'superadmin', 'admin', 'farm_manager', 'farm_owner', 'caretaker', 'technician',
         'fulfillment_manager', 'packaging_supervisor', 'quality_officer', 'sales_manager',
         'sales_person', 'driver', 'accountant'}
ALIASES = {'super_admin': 'superadmin', 'owner': 'farm_owner', 'technicians': 'technician',
           'quality_assurance': 'quality_officer', 'quality_assurance_officer': 'quality_officer',
           'sales_personnel': 'sales_person', 'delivery_agent': 'driver'}

def canonical(value):
    value = str(getattr(value, 'value', value) or '').strip().lower().replace(' ', '_').replace('-', '_')
    return ALIASES.get(value, value)


def assigned_roles(profile):
    values = profile.get('roles')
    values = values if isinstance(values, list) and values else [profile.get('role')]
    return list(dict.fromkeys(canonical(v) for v in values if canonical(v) in ROLES))


def has_role(profile, role):
    return canonical(role) in assigned_roles(profile)


def effective_profile(profile, selected=None):
    roles = assigned_roles(profile)
    role = canonical(selected or profile.get('role'))
    if role not in roles:
        raise HTTPException(403, 'This role is no longer assigned to your account. Choose an available role.')
    return {**profile, 'roles': roles, 'primary_role': profile.get('role'), 'role': role}


def requested_roles(raw, primary, previous=None):
    if raw is None:
        values = assigned_roles(previous) if previous and canonical(previous.get('role')) == canonical(primary) else [canonical(primary)]
    else:
        try: values = json.loads(raw)
        except (ValueError, TypeError): raise HTTPException(422, 'Choose valid user roles.') from None
        if not isinstance(values, list) or not values or len(values) > len(ROLES):
            raise HTTPException(422, 'Choose at least one user role.')
    result = list(dict.fromkeys(canonical(v) for v in values))
    if any(value not in ROLES for value in result) or canonical(primary) not in result:
        raise HTTPException(422, 'The primary role must be one of the assigned roles.')
    return result


def check_role_assignment(actor, roles, previous=None):
    if actor.get('status') != 'Active' or actor.get('role') not in {'admin', 'superadmin'}:
        raise HTTPException(403, 'Only active administrators can manage user roles.')
    if actor['role'] != 'superadmin' and ('superadmin' in roles or (previous and has_role(previous, 'superadmin'))):
        raise HTTPException(403, 'Only Super Admin can manage Super Admin accounts.')
