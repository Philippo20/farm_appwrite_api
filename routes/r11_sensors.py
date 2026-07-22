import os
import re

from fastapi import APIRouter, Body, Form, Header, HTTPException, status as http_status
from typing import Annotated, Optional
from enum import Enum
from datetime import datetime, timezone, date, time
from main import (
    db_id,
    db_collection_id2,
    db_collection_id11,
    db_collection_id18,
    db_collection_id21,
)
from db import db
from appwrite.id import ID
from appwrite.query import Query


collection11_router = APIRouter(tags=["Sensors"])
CONFIG_DOCUMENT_ID = "global"

class SensorType(str, Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "Carbon Dioxide"
    LIGHT = "light"
    PH_LEVEL = "pH Level"
    EC_LEVEL = "EC Level"
    WATER_LEVEL = "Water level"
    ELECTRICITY_CURRENT = "electricity_current"
    ELECTRICITY_VOLTAGE = "electricity_voltage"
    ELECTRICITY_WATTAGE = "electricity_wattage"

class Status(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    FAULTY= "Faulty"
    MAINTENANCE= "Maintenance"


def _sensor_document_payload(
    *,
    farmID: str,
    farm_name: str,
    sensortype: str,
    model_number: str,
    serial_number: str,
    location: str,
    value: float,
    status_value: str,
    unit: str,
    alerts_enabled: bool,
    maintenance_frequency: str,
    timestamp: str,
    last_maintenance_date: str,
    range_min: Optional[float] = None,
    range_max: Optional[float] = None,
    warning_min: Optional[float] = None,
    warning_max: Optional[float] = None,
) -> dict:
    data = {
        "farmID": farmID,
        "farm_name": farm_name,
        "sensortype": sensortype,
        "model_number": model_number,
        "serial_number": serial_number,
        "location": location,
        "value": value,
        "status": status_value,
        "unit": unit,
        "alerts_enabled": alerts_enabled,
        "maintenance_frequency": maintenance_frequency,
        "timestamp": timestamp,
        "last_maintenance_date": last_maintenance_date,
    }
    if range_min is not None:
        data["range_min"] = range_min
    if range_max is not None:
        data["range_max"] = range_max
    if warning_min is not None:
        data["warning_min"] = warning_min
    if warning_max is not None:
        data["warning_max"] = warning_max
    return data


def _float_or_none(value):
    if value is None or value == "":
        return None
    return float(value)


def _bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ["1", "true", "yes", "on"]
    return bool(value)


def _serial_prefix(farm_name: str, farm_id: str) -> str:
    source = farm_name or farm_id or "FARM"
    prefix = re.sub(r"[^A-Za-z0-9]+", "-", source.upper()).strip("-")
    return prefix[:40] or "FARM"


def _next_sensor_serial_number(farm_id: str, farm_name: str) -> str:
    prefix = _serial_prefix(farm_name, farm_id)
    result = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id11,
        queries=[Query.equal("farmID", [farm_id])],
    )
    used = {
        str(doc.get("serial_number") or "").strip()
        for doc in result.get("documents", [])
        if str(doc.get("serial_number") or "").strip()
    }
    next_number = len(used) + 1

    while True:
        serial_number = f"{prefix}-{next_number:03d}"
        exists = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id11,
            queries=[Query.equal("serial_number", [serial_number])],
        )
        if exists["total"] == 0:
            return serial_number
        next_number += 1


def _record_sensor_reading(
    *,
    sensor_id: str,
    serial_number: str,
    farm_id: str,
    farm_name: str,
    sensortype: str,
    value: float,
    unit: str,
    status_value: str,
    timestamp: str,
    source: str,
) -> None:
    if not db_collection_id21:
        return
    try:
        db.create_document(
            database_id=db_id,
            collection_id=db_collection_id21,
            document_id=ID.unique(),
            data={
                "sensor_id": sensor_id,
                "serial_number": serial_number,
                "farmID": farm_id,
                "farm_name": farm_name,
                "sensortype": sensortype,
                "value": value,
                "unit": unit,
                "status": status_value,
                "timestamp": timestamp,
                "source": source,
            },
        )
    except Exception as error:
        print(f"Sensor reading history write failed: {error}")


def _sensor_status_for_value(value: float, payload: dict, existing: Optional[dict] = None) -> str:
    source = {**(existing or {}), **payload}
    warning_min = _float_or_none(source.get("warning_min"))
    warning_max = _float_or_none(source.get("warning_max"))
    range_min = _float_or_none(source.get("range_min"))
    range_max = _float_or_none(source.get("range_max"))

    if warning_min is not None and value < warning_min:
        return Status.FAULTY.value
    if warning_max is not None and value > warning_max:
        return Status.FAULTY.value
    if range_min is not None and value < range_min:
        return Status.MAINTENANCE.value
    if range_max is not None and value > range_max:
        return Status.MAINTENANCE.value
    return Status.ACTIVE.value


def _validate_sensor_key(x_sensor_key: Optional[str], farm_id: Optional[str]) -> None:
    farm_key = ""
    if farm_id and db_collection_id2:
        try:
            farm = db.get_document(
                database_id=db_id,
                collection_id=db_collection_id2,
                document_id=farm_id,
            )
            farm_key = str(farm.get("sensor_ingest_api_key") or "").strip()
        except Exception:
            pass

    if farm_key:
        expected_keys = {farm_key}
    else:
        expected_keys = {
            key for key in [os.getenv("SENSOR_INGEST_API_KEY", "").strip()] if key
        }

    if not farm_key and db_collection_id18:
        try:
            config = db.get_document(
                database_id=db_id,
                collection_id=db_collection_id18,
                document_id=CONFIG_DOCUMENT_ID,
            )
            config_key = str(config.get("sensor_ingest_api_key") or "").strip()
            if config_key:
                expected_keys.add(config_key)
        except Exception:
            pass

    if expected_keys and x_sensor_key not in expected_keys:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid sensor ingestion key",
        )

@collection11_router.post("/sensors/info")
def register_sensors_info(
        farmID: Annotated[str, Form()],
        farm_name: Annotated[str, Form()],
        sensortype: Annotated[SensorType, Form()],
        model_number: Annotated[str, Form()],
        location: Annotated[str, Form()],
        value: Annotated[float, Form()],
        status: Annotated[Status, Form()],
        unit: Annotated[str, Form()],
        alerts_enabled: Annotated[bool, Form()],
        maintenance_frequency: Annotated[str, Form()],
        timestamp: Annotated[datetime, Form(...)],
        last_maintenance_date: Annotated[date, Form(...)],
        range_min: Annotated[Optional[float], Form()] = None,
        range_max: Annotated[Optional[float], Form()] = None,
        warning_min: Annotated[Optional[float], Form()] = None,
        warning_max: Annotated[Optional[float], Form()] = None,
        serial_number: Annotated[Optional[str], Form()] = None
        ):
    
    # A farm can have many sensors; serial number is the device-level unique key.
    serial_number = (serial_number or "").strip() or _next_sensor_serial_number(
        farmID,
        farm_name,
    )
    existing = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id11,
        queries=[
            Query.equal("serial_number", [serial_number])
        ]
    )
    if existing["total"] > 0:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Sensor with serial number {serial_number} already exists!")
    

    timestamp = datetime.now(timezone.utc).isoformat()

    sensors_info = _sensor_document_payload(
        farmID=farmID,
        farm_name=farm_name,
        sensortype=sensortype.value,
        model_number=model_number,
        serial_number=serial_number,
        location=location,
        value=value,
        status_value=status.value,
        unit=unit,
        alerts_enabled=alerts_enabled,
        maintenance_frequency=maintenance_frequency,
        timestamp=timestamp,
        last_maintenance_date=last_maintenance_date.isoformat(),
        range_min=range_min,
        range_max=range_max,
        warning_min=warning_min,
        warning_max=warning_max,
    )

    sensor_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id11,
        document_id=ID.unique(),
        data= sensors_info
    )
    _record_sensor_reading(
        sensor_id=sensor_create["$id"],
        serial_number=serial_number,
        farm_id=farmID,
        farm_name=farm_name,
        sensortype=sensortype.value,
        value=value,
        unit=unit,
        status_value=status.value,
        timestamp=timestamp,
        source="manual_register",
    )

    return {
        "message": "Sensor information registered successfully",
        "sensor_info_id": sensor_create["$id"],
        "serial_number": serial_number,
    }

@collection11_router.patch("/sensors/{sensors_id}")
def get_sensor_info(sensors_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id11,
            document_id= sensors_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="User not found!")


@collection11_router.get("/sensor-readings")
def get_sensor_readings():
    if not db_collection_id21:
        raise HTTPException(status_code=500, detail="APPWRITE_COLLECTION_ID21 is not configured")
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id21,
            queries=[Query.order_desc("timestamp"), Query.limit(500)],
        )
        return {"count": result["total"], "users": result["documents"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@collection11_router.get("/sensors/{serial_number}/readings")
def get_sensor_readings_by_serial(serial_number: str):
    if not db_collection_id21:
        raise HTTPException(status_code=500, detail="APPWRITE_COLLECTION_ID21 is not configured")
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id21,
            queries=[
                Query.equal("serial_number", [serial_number]),
                Query.order_desc("timestamp"),
                Query.limit(500),
            ],
        )
        return {"count": result["total"], "users": result["documents"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@collection11_router.get("/sensors")
def get_all_sensors():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id11
        )

        # Extract the list of users
        sensor_users = result["documents"]

        return {
            "count": len(sensor_users),
            "users": sensor_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@collection11_router.post("/sensors/ingest")
def ingest_sensor_reading(
    payload: dict = Body(...),
    x_sensor_key: Annotated[Optional[str], Header(alias="x-sensor-key")] = None,
):
    serial_number = str(payload.get("serial_number", "")).strip()
    if not serial_number:
        raise HTTPException(status_code=400, detail="serial_number is required")

    try:
        value = float(payload["value"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="value must be a number")

    timestamp = str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat())
    last_maintenance_date = str(
        payload.get("last_maintenance_date")
        or datetime.now(timezone.utc).date().isoformat()
    )

    existing = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id11,
        queries=[Query.equal("serial_number", [serial_number])],
    )

    if existing["total"] > 0:
        sensor = existing["documents"][0]
        farm_id = str(payload.get("farmID") or sensor.get("farmID") or "").strip()
        _validate_sensor_key(x_sensor_key, farm_id)
        status_value = str(payload.get("status") or _sensor_status_for_value(value, payload, sensor))
        update_data = {
            "value": value,
            "timestamp": timestamp,
            "status": status_value,
        }
        for key in [
            "farmID",
            "farm_name",
            "sensortype",
            "model_number",
            "location",
            "unit",
            "alerts_enabled",
            "maintenance_frequency",
            "last_maintenance_date",
            "range_min",
            "range_max",
            "warning_min",
            "warning_max",
        ]:
            if key in payload and payload[key] is not None:
                if key in ["range_min", "range_max", "warning_min", "warning_max"]:
                    update_data[key] = _float_or_none(payload[key])
                elif key == "alerts_enabled":
                    update_data[key] = _bool_value(payload[key])
                else:
                    update_data[key] = payload[key]

        updated = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id11,
            document_id=sensor["$id"],
            data=update_data,
        )
        _record_sensor_reading(
            sensor_id=updated["$id"],
            serial_number=serial_number,
            farm_id=str(updated.get("farmID") or farm_id),
            farm_name=str(updated.get("farm_name") or sensor.get("farm_name") or ""),
            sensortype=str(updated.get("sensortype") or sensor.get("sensortype") or ""),
            value=value,
            unit=str(updated.get("unit") or sensor.get("unit") or ""),
            status_value=str(updated.get("status") or status_value),
            timestamp=timestamp,
            source="ingest",
        )
        return {
            "message": "Sensor reading updated",
            "mode": "updated",
            "sensor_id": updated["$id"],
            "status": updated.get("status"),
            "timestamp": updated.get("timestamp"),
        }

    required_fields = [
        "farmID",
        "farm_name",
        "sensortype",
        "model_number",
        "location",
        "unit",
    ]
    missing = [field for field in required_fields if not str(payload.get(field, "")).strip()]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown serial_number. First reading must include: {', '.join(missing)}",
        )

    _validate_sensor_key(x_sensor_key, str(payload.get("farmID") or "").strip())

    status_value = str(payload.get("status") or _sensor_status_for_value(value, payload))
    sensor_data = _sensor_document_payload(
        farmID=str(payload["farmID"]),
        farm_name=str(payload["farm_name"]),
        sensortype=str(payload["sensortype"]),
        model_number=str(payload["model_number"]),
        serial_number=serial_number,
        location=str(payload["location"]),
        value=value,
        status_value=status_value,
        unit=str(payload["unit"]),
        alerts_enabled=_bool_value(payload.get("alerts_enabled", True)),
        maintenance_frequency=str(payload.get("maintenance_frequency", "Monthly")),
        timestamp=timestamp,
        last_maintenance_date=last_maintenance_date,
        range_min=_float_or_none(payload.get("range_min")),
        range_max=_float_or_none(payload.get("range_max")),
        warning_min=_float_or_none(payload.get("warning_min")),
        warning_max=_float_or_none(payload.get("warning_max")),
    )

    created = db.create_document(
        database_id=db_id,
        collection_id=db_collection_id11,
        document_id=ID.unique(),
        data=sensor_data,
    )
    _record_sensor_reading(
        sensor_id=created["$id"],
        serial_number=serial_number,
        farm_id=str(payload["farmID"]),
        farm_name=str(payload["farm_name"]),
        sensortype=str(payload["sensortype"]),
        value=value,
        unit=str(payload["unit"]),
        status_value=str(created.get("status") or status_value),
        timestamp=timestamp,
        source="ingest",
    )
    return {
        "message": "Sensor registered and reading ingested",
        "mode": "created",
        "sensor_id": created["$id"],
        "status": created.get("status"),
        "timestamp": created.get("timestamp"),
    }
    
@collection11_router.put("/sensors/{sensors_id}")
def update_sensor(
    sensors_id:str,
    farmID: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    sensortype: Annotated[SensorType, Form()],
    model_number: Annotated[str, Form()],
    location: Annotated[str, Form()],
    value: Annotated[float, Form()],
    status: Annotated[Status, Form()],
    unit: Annotated[str, Form()],
    alerts_enabled: Annotated[bool, Form()],
    maintenance_frequency: Annotated[str, Form()],
    timestamp: Annotated[datetime, Form(...)],
    last_maintenance_date: Annotated[date, Form(...)],
    range_min: Annotated[Optional[float], Form()] = None,
    range_max: Annotated[Optional[float], Form()] = None,
    warning_min: Annotated[Optional[float], Form()] = None,
    warning_max: Annotated[Optional[float], Form()] = None,
    serial_number: Annotated[Optional[str], Form()] = None
    ):
    
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        previous_sensor = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id11,
            document_id=sensors_id,
        )
        resolved_serial_number = (
            (serial_number or "").strip()
            or str(previous_sensor.get("serial_number") or "").strip()
            or _next_sensor_serial_number(farmID, farm_name)
        )
        sensors_info = _sensor_document_payload(
            farmID=farmID,
            farm_name=farm_name,
            sensortype=sensortype.value,
            model_number=model_number,
            serial_number=resolved_serial_number,
            location=location,
            value=value,
            status_value=status.value,
            unit=unit,
            alerts_enabled=alerts_enabled,
            maintenance_frequency=maintenance_frequency,
            timestamp=timestamp,
            last_maintenance_date=last_maintenance_date.isoformat(),
            range_min=range_min,
            range_max=range_max,
            warning_min=warning_min,
            warning_max=warning_max,
        )

        updated_sensor_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id11,
            document_id=sensors_id,
            data=sensors_info,
            permissions=[]
        )
        _record_sensor_reading(
            sensor_id=sensors_id,
            serial_number=resolved_serial_number,
            farm_id=farmID,
            farm_name=farm_name,
            sensortype=sensortype.value,
            value=value,
            unit=unit,
            status_value=status.value,
            timestamp=timestamp,
            source="manual_update",
        )
        return {"message": "Sensor info updated successfully", "user": updated_sensor_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection11_router.delete("/sensors/{sensors_id}")
def delete_sensor(sensors_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id11, 
            document_id=sensors_id)
        return {"message": f"User with ID {sensors_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
