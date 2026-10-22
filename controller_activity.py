"""V1.8 activity contract. Outputs are controller reports, not flow/current sensors."""
import hashlib
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

Counter = Annotated[int, Field(strict=True, ge=0, le=4294967295)]
Timestamp = Annotated[int, Field(strict=True, ge=0, le=253402300799)]
ACTIVITY_TYPES = ('controller.status', 'fertigation.racks_changed', 'lights.changed',
    'fertigation.started', 'fertigation.stopped', 'fertigation.feeding_started',
    'fertigation.feeding_stopped', 'fertigation.state_changed', 'fertigation.paused',
    'fertigation.resumed', 'drainage.started', 'drainage.stopped', 'grid.changed',
    'rtc.changed', 'command.rejected', 'fertigation.recovery_queued',
    'fertigation.recovery_started', 'fertigation.recovery_completed',
    'fertigation.recovery_cancelled')
EQUIPMENT_OUTPUTS = {
    'grow_light': {'lights.E': 'Light E', 'lights.F': 'Light F', 'lights.P': 'Light P'},
    'feeding_pump': {'fertigation.pump_on': 'Fertigation pump (D12)'},
    'drainage_pump': {'drainage.ef.pump_on': 'Shared E/F drainage (D11)',
                      'drainage.p.pump_on': 'P drainage (D10)'},
}

class Fields(BaseModel):
    model_config = ConfigDict(extra='forbid')

class RackMask(Fields):
    E: StrictBool
    F: StrictBool
    P: StrictBool

class Lights(RackMask):
    pair: Literal['E+F', 'F+P', 'P+E', 'OFF', 'OTHER']
    changing: StrictBool

class Feeding(Fields):
    rack: Literal['E', 'F', 'P'] | None
    started_uptime_ms: Counter | None
    started_rtc_unix_s: Timestamp | None

class Fertigation(Fields):
    enabled: RackMask
    state: Literal['idle', 'opening_valve', 'feeding', 'closing_valve', 'paused_grid',
        'calibration_waiting', 'calibration_starting', 'calibration_feeding', 'rtc_unavailable']
    active: StrictBool
    pump_on: StrictBool
    rack: Literal['E', 'F', 'P'] | None
    source: Literal['scheduled', 'manual', 'calibration']
    manual_requested: StrictBool
    configured_duration_ms: Counter
    started_uptime_ms: Counter | None
    started_rtc_unix_s: Timestamp | None
    feeding: Feeding

class DrainPump(Fields):
    pump_on: StrictBool
    tank_full: StrictBool
    started_uptime_ms: Counter | None
    started_rtc_unix_s: Timestamp | None

class Drainage(Fields):
    ef: DrainPump
    p: DrainPump

class ControllerActivityEvent(Fields):
    event_id: str = Field(min_length=3, max_length=100)
    session_id: str = Field(min_length=8, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    command_id: str | None = Field(default=None, max_length=36)
    category: Literal['activity', 'controller'] | None = None
    type: Literal['controller.status', 'fertigation.racks_changed', 'lights.changed',
        'fertigation.started', 'fertigation.stopped', 'fertigation.feeding_started',
        'fertigation.feeding_stopped', 'fertigation.state_changed', 'fertigation.paused',
        'fertigation.resumed', 'drainage.started', 'drainage.stopped', 'grid.changed',
        'rtc.changed', 'command.rejected', 'fertigation.recovery_queued',
        'fertigation.recovery_started', 'fertigation.recovery_completed',
        'fertigation.recovery_cancelled']
    target: str = Field(default='', max_length=32)
    reason: str | None = Field(default=None, max_length=64)
    message: str = Field(default='', max_length=1000)
    uptime_ms: Counter
    rtc_unix_s: Timestamp | None
    rtc_available: StrictBool
    grid_available: StrictBool
    lights: Lights
    fertigation: Fertigation
    drainage: Drainage

    @model_validator(mode='after')
    def valid_identity(self):
        suffix = self.event_id.removeprefix(self.session_id + '-')
        if not self.event_id.startswith(self.session_id + '-') or not suffix.isascii() or not suffix.isdecimal():
            raise ValueError('Activity event_id must be session_id followed by a numeric generation.')
        if len(suffix) > 16 or int(suffix) > 9007199254740991:
            raise ValueError('Activity generation is too large.')
        if suffix != str(int(suffix)):
            raise ValueError('Use the canonical numeric generation without leading zeros.')
        if self.command_id:
            from uuid import UUID
            self.command_id = str(UUID(self.command_id))
        else:
            self.command_id = None
        if self.type == 'command.rejected' and not self.reason:
            raise ValueError('Command rejection requires a reason.')
        return self

    @property
    def generation(self):
        return int(self.event_id.rsplit('-', 1)[1])

def activity_key(sensor_id, event_id):
    return hashlib.sha256(f'{sensor_id}:{event_id}'.encode()).hexdigest()[:36]

def output_value(snapshot, output):
    value = snapshot
    for part in output.split('.'):
        value = value.get(part) if isinstance(value, dict) else None
    return value if isinstance(value, bool) else None

def reported_elapsed(snapshot, output):
    if output.startswith('lights.') or not output_value(snapshot, output):
        return None
    pump = snapshot.get('fertigation', {}).get('feeding', {}) if output.startswith('fertigation.') else snapshot.get('drainage', {}).get(output.split('.')[1], {})
    start = pump.get('started_uptime_ms')
    return ((snapshot['uptime_ms'] - start) & 0xffffffff) if isinstance(start, int) else None
