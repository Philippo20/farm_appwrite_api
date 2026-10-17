"""Validated controller calibration events and deterministic replay policy."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

EVENT_TYPES = [f'calibration.{name}' for name in (
    'request_received', 'waiting_for_start', 'starting', 'running',
    'completed', 'cancelled', 'rejected', 'not_saved')]
TERMINAL = {'calibration.completed', 'calibration.cancelled', 'calibration.not_saved'}
NOTIFIABLE = TERMINAL | {'calibration.rejected'}
PHASE = {name: rank for rank, name in enumerate(EVENT_TYPES, 1)}
REASONS = Literal['grid_power_lost', 'grid_power_unavailable', 'tank_not_full',
    'all_racks_disabled', 'selected_rack_disabled', 'calibration_already_running',
    'no_calibration_selected', 'pump_start_delay', 'pump_not_started',
    'maximum_duration_reached', 'duration_too_short', 'user_cancelled', 'command_expired']
Nonnegative = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]

class CalibrationEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Literal['calibration'] = 'calibration'
    event_id: UUID
    session_id: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    calibration_id: UUID
    command_id: UUID
    type: Literal['calibration.request_received', 'calibration.waiting_for_start',
        'calibration.starting', 'calibration.running', 'calibration.completed',
        'calibration.cancelled', 'calibration.rejected', 'calibration.not_saved']
    target: Literal['ef_drain', 'p_drain', 'fertigation']
    rack: Literal['E', 'F', 'P'] | None = None
    state: str = Field(min_length=1, max_length=64)
    reason: REASONS | None = None
    message: str = Field(default='', max_length=1000)
    uptime_ms: Nonnegative
    grid_available: StrictBool | None = None
    elapsed_ms: Nonnegative | None = None
    saved: StrictBool = False
    saved_duration_ms: Nonnegative | None = None

    @model_validator(mode='after')
    def coherent(self):
        if (self.target == 'fertigation') != (self.rack is not None):
            raise ValueError('Fertigation requires rack E, F or P; drainage events must omit rack.')
        if self.type in {'calibration.cancelled', 'calibration.rejected', 'calibration.not_saved'} and not self.reason:
            raise ValueError('Cancellation, rejection and not-saved events require a reason.')
        completed = self.type == 'calibration.completed'
        if completed and (not self.saved or not self.saved_duration_ms):
            raise ValueError('Completion requires saved=true and a positive saved_duration_ms.')
        if not completed and (self.saved or self.saved_duration_ms is not None):
            raise ValueError('Only completion events may save a duration.')
        return self

def event_order(event):
    return (event['uptime_ms'], PHASE[event['type']], event['event_id'])

def session_view(events):
    """Terminal results survive delayed progress; a rejected repeat cannot stop a running pump."""
    terminal = [e for e in events if e['type'] in TERMINAL]
    progress = [e for e in events if e['type'] != 'calibration.rejected']
    latest = max(events, key=event_order)
    if terminal:
        current = max(terminal, key=event_order)
    elif progress:
        current = max(progress, key=lambda e: (PHASE[e['type']], *event_order(e)))
        if latest['type'] == 'calibration.rejected' and current['type'] != 'calibration.running':
            current = latest
    else:
        current = latest
    return {'calibration_id': current['calibration_id'], 'session_id': current['session_id'],
        'target': current['target'], 'rack': current.get('rack'),
        'selection_at': current['selection_at'], 'status': current['type'].split('.')[-1],
        'event': current, 'latest_event': latest}

def target_label(event):
    return {'ef_drain': 'EF Drain', 'p_drain': 'P Drain',
        'fertigation': f"Fertigation · Rack {event.get('rack', '')}"}[event['target']]

def notification_for(event, sensor, actor_id):
    if event['type'] not in NOTIFIABLE:
        return None
    status = event['type'].split('.')[-1].replace('_', ' ')
    detail = event.get('message') or (event.get('reason') or status).replace('_', ' ').capitalize()
    if event['saved']:
        detail += f" Saved duration: {event['saved_duration_ms'] / 1000:g} seconds."
    return {'title': f'Calibration {status}',
        'message': f"{sensor['serial_number']} · {target_label(event)}: {detail}",
        'kind': 'maintenance', 'priority': 'normal' if event['saved'] else 'high',
        'farm': sensor['farmID'], 'roles': {'admin', 'superadmin', 'super_admin'},
        'recipients': {actor_id}}
