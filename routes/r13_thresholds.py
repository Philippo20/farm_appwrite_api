from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from main import db_id, db_collection_id13
from db import db
from appwrite.id import ID
from appwrite.query import Query


collection13_router = APIRouter(tags=["Thresholds"])

@collection13_router.post("/thresholds/info")
def register_sensors_info(
        farmID: Annotated[str, Form()],
        temperature_max: Annotated[float, Form()],
        temperature_min: Annotated[float, Form()],
        ph_min: Annotated[float, Form()],
        ph_max: Annotated[float, Form()],
        ec_max: Annotated[float, Form()],
        humidity_max: Annotated[float, Form()] = None
        ):
    # Ensure an todos with farmID does not exist
    existing = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id13,
        queries=[
            Query.equal("farmID", [farmID])
        ]
    )
    if existing["total"] > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Advert with farmID: {farmID} already exist!")


    thresholds_info = {
        "farmID": farmID,
        "temperature_max": temperature_max,
        "temperature_min": temperature_min,
        "ph_min": ph_min,
        "ph_max": ph_max,
        "ec_max": ec_max,
        "humidity_max": humidity_max
    }

    thresholds_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id13,
        document_id=ID.unique(),
        data= thresholds_info
    )

    return {
        "message": "Threshold information registered successfully",
        "threshold_info_id": thresholds_create["$id"]
    }

@collection13_router.get("/thresholds")
def get_all_thresholds():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id13
        )

        # Extract the list of users
        thresholds_users = result["documents"]

        return {
            "count": len(thresholds_users),
            "users": thresholds_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection13_router.get("/thresholds/{thresholds_id}")
def get_threshold_info(thresholds_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id13,
            document_id= thresholds_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection13_router.put("/thresholds/{thresholds_id}")
def update_threshold(
    thresholds_id:str,
    farmID: Annotated[str, Form()],
    temperature_max: Annotated[float, Form()],
    temperature_min: Annotated[float, Form()],
    ph_min: Annotated[float, Form()],
    ph_max: Annotated[float, Form()],
    ec_max: Annotated[float, Form()],
    humidity_max: Annotated[float, Form()] = None):
    
    try:
        # Perform update
        updated_threshold_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id13,
            document_id=thresholds_id,
            data={"farmID": farmID,
                  "temperature_max": temperature_max,
                  "temperature_min": temperature_min,
                  "ph_min": ph_min,
                  "ph_max": ph_max,
                  "ec_max": ec_max,
                  "humidity_max": humidity_max
            },
            permissions=[]
        )
        return {"message": "Threshold info updated successfully", "user": updated_threshold_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection13_router.delete("/thresholds/{thresholds_id}")
def delete_threshold(thresholds_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id13, 
            document_id=thresholds_id)
        return {"message": f"User with ID {thresholds_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))