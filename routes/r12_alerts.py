from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, timezone
from main import db_id, db_collection_id12
from db import db
from appwrite.id import ID
from appwrite.query import Query


collection12_router = APIRouter(tags=["Alerts"])

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class sensorType(str, Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "CO2"
    LIGHT = "light"
    PH = "pH"
    EC = "ec"
    ELECTRICITY_CURRENT = "electricity_current"
    ELECTRICITY_VOLTAGE = "electricity_voltage"
    ELECTRICITY_WATTAGE = "electricity_wattage"

@collection12_router.post("/alerts/info")
def register_alerts_info(
        message: Annotated[str, Form()],
        sensorType: Annotated[sensorType, Form()],
        severity: Annotated[Severity, Form()],
        resolved: Annotated[bool, Form()] = False
        ):    
    timestamp = datetime.now(timezone.utc).isoformat()

    alerts_info = {
        "farmID": ID.unique(),
        "message": message,
        "sensorType": sensorType,
        "severity": severity,
        "timestamp": timestamp,
        "resolved": resolved
    }

    alert_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id12,
        document_id=ID.unique(),
        data= alerts_info
    )

    return {
        "message": "Alert information registered successfully",
        "alert_info_id": alert_create["$id"]
    }

@collection12_router.get("/alerts")
def get_all_alerts():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id12
        )

        # Extract the list of users
        alert_users = result["documents"]

        return {
            "count": len(alert_users),
            "users": alert_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection12_router.get("/alerts/{alerts_id}")
def get_alert_info(alerts_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id12,
            document_id= alerts_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection12_router.put("/alerts/{alerts_id}")
def update_alert(
    alerts_id:str,
    farmID: Annotated[str, Form()],
    message: Annotated[str, Form()],
    sensorType: Annotated[sensorType, Form()],
    severity: Annotated[Severity, Form()],
    resolved: Annotated[bool, Form()] = False
    ):
    
    # timestamp = datetime.now(timezone.utc).isoformat()
    timestamp = timezone

    try:
        # Perform update
        updated_alert_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id12,
            document_id=alerts_id,
            data={
                "farmID": farmID,
                "message": message,
                "sensorType": sensorType,
                "severity": severity,
                "timestamp": timestamp,
                "resolved": resolved
                },
            permissions=[]
        )
        return {"message": "Sensor info updated successfully", "user": updated_alert_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection12_router.delete("/alerts/{alerts_id}")
def delete_sensor(alerts_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id12, 
            document_id=alerts_id)
        return {"message": f"User with ID {alerts_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))