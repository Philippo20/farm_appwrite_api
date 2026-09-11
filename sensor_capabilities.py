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
    return {**sensor, "calibration_required": sensor_calibration_required(sensor), "maintenance_required": sensor_maintenance_required(sensor)}


def sensor_maintenance_required(sensor: dict) -> bool:
    raw = str(sensor.get("sensortype") or sensor.get("sensor_type") or sensor.get("type") or "")
    kind = re.sub(r"[^a-z0-9]", "", raw.lower().replace("₂", "2"))
    return kind not in {"temperature", "temp", "humidity", "relativehumidity", "vpd",
                        "vaporpressuredeficit", "vapourpressuredeficit", "light", "lightintensity",
                        "co2", "carbondioxide"}


def maintenance_values(kind, frequency, last_date):
    if not sensor_maintenance_required({"sensortype": kind}):
        return {"maintenance_frequency": "Not required", "last_maintenance_date": None}
    if not str(frequency or "").strip() or not last_date:
        raise ValueError("Maintenance frequency and last maintenance date are required for this sensor type")
    return {"maintenance_frequency": str(frequency).strip(), "last_maintenance_date": last_date}
