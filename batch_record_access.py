def can_review_records(profile, farm):
    if str(profile.get('status', '')).strip().lower() != 'active':
        return False
    role = str(profile.get('role', '')).strip().lower().replace(' ', '_')
    if role in {'admin', 'superadmin', 'super_admin'}:
        return True
    identities = {str(profile.get('$id', '')).strip(), str(profile.get('email', '')).strip()} - {''}
    return role == 'farm_manager' and any(str(farm.get(key, '')).strip() in identities
        for key in ('farm_manager_id', 'farmManagerId'))
