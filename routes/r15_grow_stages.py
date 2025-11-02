from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import time
from main import db_id, db_collection_id15
from db import db
from appwrite.id import ID
from appwrite.query import Query


collection15_router = APIRouter(tags=["Grow_stages"])

class StageName(str, Enum):
    GERMINATION = "germination"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    HARVEST = "harvest"


@collection15_router.post("/grow_stages/info")
def register_grow_stages_info(
        stage_name: Annotated[StageName, Form()],
        started: Annotated[bool, Form()],        
        created_by: Annotated[str, Form()],
        start_time: Annotated[time, Form(...)],
        end_time: Annotated[time, Form(...)]= None,
        ):

    grow_stages_info = {
        "farmID": ID.unique(),
        "stage_name": stage_name,
        "started": started,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "created_by": created_by
    }

    grow_stage_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id15,
        document_id=ID.unique(),
        data= grow_stages_info
    )

    return {
        "message": "Grow_stages information registered successfully",
        "grow_stage_info_id": grow_stage_create["$id"]
    }

@collection15_router.get("/grow_stages")
def get_all_grow_stage():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id15
        )

        # Extract the list of users
        grow_stage_users = result["documents"]

        return {
            "count": len(grow_stage_users),
            "users": grow_stage_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection15_router.get("/sensors/{sensors_id}")
def get_sensor_info(sensors_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id15,
            document_id= sensors_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection15_router.put("/grow_stages/{grow_stages_id}")
def update_grow_stages(
    grow_stages_id:str,
    farmID: Annotated[str, Form()],
    stage_name: Annotated[StageName, Form()],
    started: Annotated[bool, Form()],
    created_by: Annotated[str, Form()],
    start_time: Annotated[time, Form(...)],
    end_time: Annotated[time, Form(...)]= None
    ):
    try:
        # Perform update
        updated_sensor_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id15,
            document_id=grow_stages_id,
            data={"farmID": farmID,
                  "stage_name": stage_name,
                  "started": started,
                  "start_time": start_time.isoformat(),
                  "end_time": end_time.isoformat(),
                  "created_by": created_by
            },
            permissions=[]
        )
        return {"message": "Grow_stage info updated successfully", "user": updated_sensor_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection15_router.delete("/grow_stages/{grow_stages_id}")
def delete_grow_stage(grow_stage_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id15, 
            document_id=grow_stage_id)
        return {"message": f"User with ID {grow_stage_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))