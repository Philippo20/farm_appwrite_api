"""Named command configuration. Payloads are data for firmware, never server code."""
import hashlib
import json
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, ValidationError
from fastapi import HTTPException

class NamedCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=36,
                                        pattern=r'^[A-Za-z0-9_-]+$')]
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]

_commands = TypeAdapter(Annotated[list[NamedCommand], Field(min_length=1, max_length=12)])

def configured_commands(raw, required=True):
    try:
        values = json.loads(raw) if isinstance(raw, str) else raw
        if not values and not required:
            return []
        commands = [command.model_dump() for command in _commands.validate_python(values)]
        if len({command['id'] for command in commands}) != len(commands):
            raise ValueError('Command identifiers must be unique.')
        if len({command['label'].casefold() for command in commands}) != len(commands):
            raise ValueError('Use a different name for each command.')
        if any(any(ord(char) < 32 or ord(char) == 127 for char in command[field])
               for command in commands for field in ('label', 'value')):
            raise ValueError('Command names and values must contain printable text.')
        return commands
    except (ValidationError, TypeError, ValueError) as error:
        detail = str(error) if isinstance(error, ValueError) and not isinstance(error, ValidationError) else ''
        raise HTTPException(422, detail or 'Configure 1–12 named commands with a name (60 characters maximum) and value (256 characters maximum).') from error

def serialize_commands(raw):
    return json.dumps(configured_commands(raw), ensure_ascii=False, separators=(',', ':'))

def config_revision(sensor):
    data = serialize_commands(sensor.get('command_config'))
    identity = [sensor.get('farmID'), sensor.get('serial_number'), sensor.get('status'), sensor.get('$updatedAt'), data]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
