from farm_assignments import is_farm_caretaker
"""Pure policies for authenticated, short-lived relay commands."""
from datetime import datetime, timezone

OFFLINE_SECONDS = 15
COMMAND_SECONDS = 10

def now_utc():
    return datetime.now(timezone.utc)

def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None

def online(heartbeat, now):
    at = parse_time(heartbeat.get('seen_at')) if heartbeat else None
    return at is not None and 0 <= (now-at).total_seconds() <= OFFLINE_SECONDS

def command_live(command, heartbeat, now):
    expiry = parse_time(command.get('expires_at')) if command else None
    return bool(command and heartbeat and expiry and now < expiry and
                command.get('session_id') == heartbeat.get('session_id') and online(heartbeat, now))

def can_control(profile, farm):
    if str(profile.get('status', '')).lower() != 'active':
        return False
    role = str(profile.get('role', '')).lower().replace(' ', '_')
    if role in ('superadmin', 'super_admin', 'admin'):
        return True
    if role == 'caretaker': return is_farm_caretaker(farm, profile)
    field = {'farm_owner': 'ownerID'}.get(role)
    identities = {str(profile.get('$id', '')), str(profile.get('email', ''))} - {''}
    return bool(field and str(farm.get(field, '')) in identities)
