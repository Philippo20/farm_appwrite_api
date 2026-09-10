"""Application maintenance defaults, not a claim about factory calibration."""
import re


def sensor_calibration_required(sensor: dict):
    override = sensor.get("calibration_required")
    if isinstance(override, bool):
        return override
    kind = re.sub(r"[^a-z0-9]", "", str(sensor.get("sensortype") or sensor.get("sensor_type") or sensor.get("type") or "").lower())
    if kind in {"temperature", "temp"}:
        return False
    if kind in {"ph", "phlevel", "ec", "eclevel", "conductivity", "electricalconductivity", "tds"}:
        return True
    return None


def with_sensor_capabilities(sensor: dict) -> dict:
    return {**sensor, "calibration_required": sensor_calibration_required(sensor)}
