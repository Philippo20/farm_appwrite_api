from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, timezone, date, time
from main import db_id, db_collection_id11
from db import db
from appwrite.id import ID
from appwrite.query import Query


collection11_router = APIRouter(tags=["Sensors"])

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

@collection11_router.post("/sensors/info")
def register_sensors_info(
        farmID: Annotated[str, Form()],
        farm_name: Annotated[str, Form()],
        sensortype: Annotated[SensorType, Form()],
        model_number: Annotated[str, Form()],
        serial_number: Annotated[str, Form()],
        location: Annotated[str, Form()],
        value: Annotated[float, Form()],
        status: Annotated[Status, Form()],
        unit: Annotated[str, Form()],
        alerts_enabled: Annotated[bool, Form()],
        maintenance_frequency: Annotated[str, Form()],
        timestamp: Annotated[datetime, Form(...)],
        last_maintenance_date: Annotated[date, Form(...)]
        ):
    
    # Ensure an todos with farmID does not exist
    existing = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id11,
        queries=[
            Query.equal("farmID", [farmID])
        ]
    )
    if existing["total"] > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Advert with farmID: {farmID} already exist!")
    

    timestamp = datetime.now(timezone.utc).isoformat()

    sensors_info = {
        "farmID": farmID,
        "farm_name": farm_name,
        "sensortype": sensortype,
        "model_number": model_number,
        "serial_number": serial_number,
        "location": location,
        "value": value,
        "status": status,
        "unit": unit,
        "alerts_enabled": alerts_enabled,
        "maintenance_frequency": maintenance_frequency,
        "timestamp": timestamp,
        "last_maintenance_date": last_maintenance_date.isoformat()
    }

    sensor_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id11,
        document_id=ID.unique(),
        data= sensors_info
    )

    return {
        "message": "Sensor information registered successfully",
        "sensor_info_id": sensor_create["$id"]
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")

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
    
@collection11_router.put("/sensors/{sensors_id}")
def update_sensor(
    sensors_id:str,
    farmID: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    sensortype: Annotated[SensorType, Form()],
    model_number: Annotated[str, Form()],
    serial_number: Annotated[str, Form()],
    location: Annotated[str, Form()],
    value: Annotated[float, Form()],
    status: Annotated[Status, Form()],
    unit: Annotated[str, Form()],
    alerts_enabled: Annotated[bool, Form()],
    maintenance_frequency: Annotated[str, Form()],
    timestamp: Annotated[datetime, Form(...)],
    last_maintenance_date: Annotated[date, Form(...)]
    ):
    
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        # Perform update
        updated_sensor_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id11,
            document_id=sensors_id,
            data={"farmID": farmID,
                  "farm_name": farm_name,
                  "sensortype": sensortype,
                  "model_number": model_number,
                  "serial_number": serial_number,
                  "location": location,
                  "value": value,
                  "status": status,
                  "unit": unit,
                  "alerts_enabled": alerts_enabled,
                  "maintenance_frequency": maintenance_frequency,
                  "timestamp": timestamp,
                  "last_maintenance_date": last_maintenance_date.isoformat()
            },
            permissions=[]
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