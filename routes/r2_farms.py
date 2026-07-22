import secrets

from fastapi import APIRouter, Body, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id2
from db import db
from appwrite.id import ID
from appwrite.query import Query
from audit_utils import write_audit

collection2_router = APIRouter(tags=["Farms"])


def _generate_sensor_key() -> str:
    return f"fs_farm_sensor_{secrets.token_urlsafe(32)}"

class TierType(str, Enum):
    COMPACT = "Compact"
    MEDIUM = "Medium"
    MEGA = "Mega"


class Status(str, Enum):
    ACTIVE = "Active"
    PENDING = "Pending"
    SUSPENDED = "Suspended"

@collection2_router.post("/farms/info")
def register_farm(
        name: Annotated[str, Form()],
        location: Annotated[str, Form()],
        plant_type: Annotated[str, Form()],
        plant_variety: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        tier_type: Annotated[TierType, Form()],
        ownerID: Annotated[str, Form()] = "Unassigned",
        caretakerID: Annotated[str, Form()] = "Unassigned",
        farm_manager_id: Annotated[str, Form()] = "Unassigned",
        technician_id: Annotated[str, Form()] = "Unassigned"
        ):
    
    # Ensure farm info with name and caretakerID combined does not exist
    existing = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id2,
        queries=[
            Query.equal("name", [name])
        ]
    )
    if existing["total"] > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Farm with name: {name} already exists!")
    

    farms_info = {
        "name": name,
        "location": location,
        "ownerID": ownerID,
        "caretakerID": caretakerID,
        "farm_manager_id": farm_manager_id,
        "technician_id": technician_id,
        "plant_type": plant_type,
        "plant_variety": plant_variety,
        "tier_type": tier_type,
        "status": status,
        "sensor_ingest_api_key": _generate_sensor_key(),
    }
    print(farms_info)

    farm_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id2,
        document_id=ID.unique(),
        data= farms_info
    )
    write_audit(
        action_type="Create",
        collection_name="Farms",
        performed_by_id=ownerID,
        performed_by_role="farm_owner",
        action_details=f"Created farm {name}",
        new_data=farms_info
    )

    return {
        "message": "Farms details registered successfully",
        "farm_info_id": farm_create["$id"]
    }

@collection2_router.get("/farms")
def get_all_farm_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id2
        )

        # Extract the list of users
        farm_users = result["documents"]

        return {
            "count": len(farm_users),
            "users": farm_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection2_router.get("/farm/{farm_id}")
def get_farm_info(farm_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id2,
            document_id= farm_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection2_router.put("/farms/{farm_id}")
def update_farm(
    farm_id:str,
    name: Annotated[str, Form(...)],
    location: Annotated[str, Form(...)],
    ownerID: Annotated[str, Form()],
    plant_type: Annotated[str, Form()],
    plant_variety: Annotated[str, Form()],
    status: Annotated[Status, Form()],
    tier_type: Annotated[TierType, Form()],
    caretakerID: Annotated[str, Form()],
    farm_manager_id: Annotated[str, Form()] = "Unassigned",
    technician_id: Annotated[str, Form()] = "Unassigned"):

    try:
        previous_farm = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id2,
            document_id=farm_id
        )
        update_data = {"name": name,
                  "location": location,
                  "ownerID": ownerID,
                  "caretakerID": caretakerID,
                  "farm_manager_id": farm_manager_id,
                  "technician_id": technician_id,
                  "plant_type": plant_type,
                  "plant_variety": plant_variety,
                  "tier_type": tier_type,
                  "status": status
            }
        # Perform update
        updated_farm_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id2,
            document_id=farm_id,
            data=update_data,
            permissions=[]
        )
        write_audit(
            action_type="Update",
            collection_name="Farms",
            performed_by_id=ownerID,
            performed_by_role="farm_owner",
            action_details=f"Updated farm {name}",
            previous_data=previous_farm,
            new_data=update_data
        )
        return {"message": "Farm info updated successfully", "user": updated_farm_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


@collection2_router.post("/farms/{farm_id}/sensor-api-key")
def generate_farm_sensor_api_key(
    farm_id: str,
    payload: dict = Body(default={}),
):
    try:
        previous_farm = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id2,
            document_id=farm_id,
        )
        updated_by = str(payload.get("updated_by") or "system").strip()
        generated_key = _generate_sensor_key()
        updated_farm = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id2,
            document_id=farm_id,
            data={"sensor_ingest_api_key": generated_key},
        )
        write_audit(
            action_type="Update",
            collection_name="Farms",
            performed_by_id=updated_by,
            performed_by_role="superadmin",
            action_details=f"Generated sensor API key for farm {previous_farm.get('name', farm_id)}",
            previous_data={
                **previous_farm,
                "sensor_ingest_api_key": "***configured***"
                if previous_farm.get("sensor_ingest_api_key")
                else "",
            },
            new_data={"sensor_ingest_api_key": "***generated***"},
        )
        return {
            "message": "Farm sensor API key generated successfully",
            "farm": updated_farm,
            "sensor_ingest_api_key": generated_key,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sensor API key update failed: {e}")
    
@collection2_router.delete("/farms/{farm_id}")
def delete_farm_info(farm_id:str):
    try:
        previous_farm = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id2,
            document_id=farm_id
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id2, 
            document_id=farm_id)
        write_audit(
            action_type="Delete",
            collection_name="Farms",
            performed_by_id=previous_farm.get("ownerID", "system"),
            performed_by_role="superadmin",
            action_details=f"Deleted farm {previous_farm.get('name', farm_id)}",
            previous_data=previous_farm
        )
        return {"message": f"Farm with ID {farm_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
