from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id2
from db import db
from appwrite.id import ID
from appwrite.query import Query

collection2_router = APIRouter(tags=["Farms"])

class TierType(str, Enum):
    COMPACT = "Compact"
    MEDIUM = "Medium"
    MEGA = "Mega"


class Status(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@collection2_router.post("/farms/info")
def register_farm(
        name: Annotated[str, Form()],
        location: Annotated[str, Form()],
        plant_type: Annotated[str, Form()],
        plant_variety: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        tierType: Annotated[TierType, Form()],
        created_at: Annotated[date, Form(...)],
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
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Advert with name: {name} already exist!")
    

    farms_info = {
        "name": name,
        "farmID": ID.unique(),
        "location": location,
        "ownerID": ID.unique(),
        "caretakerID": ID.unique(),
        "plant_type": plant_type,
        "plant_variety": plant_variety,
        "tierType": tierType,
        "status": status,
        "created_at": created_at.isoformat()
    }
    print(farms_info)

    farm_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id2,
        document_id=ID.unique(),
        data= farms_info
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
    tierType: Annotated[TierType, Form()],
    caretakerID: Annotated[str, Form()],
    created_at: Annotated[date, Form(...)]):

    try:
        # Perform update
        updated_farm_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id2,
            document_id=farm_id,
            data={"name": name,
                  "location": location,
                  "ownerID": ownerID,
                  "caretakerID": caretakerID,
                  "plant_type": plant_type,
                  "plant_variety": plant_variety,
                  "tierType": tierType,
                  "status": status,
                  "created_at": created_at.isoformat(),
            },
            permissions=[]
        )
        return {"message": "Farm info updated successfully", "user": updated_farm_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection2_router.delete("/farms/{farm_id}")
def delete_farm_info(farm_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id2, 
            document_id=farm_id)
        return {"message": f"User with ID {farm_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))