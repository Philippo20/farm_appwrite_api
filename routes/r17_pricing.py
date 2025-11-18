from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from main import db_id, db_collection_id17
from db import db
from appwrite.id import ID
from appwrite.query import Query

collection17_router = APIRouter(tags=["Pricing"])

class Status(str, Enum):
    ACTIVE = "Active"
    FROZEN = "Inactive"

@collection17_router.post("/pricing/info")
def register_pricing_info(
        plant_type: Annotated[str, Form()],
        packaging: Annotated[str, Form()],
        regular_price: Annotated[float, Form()],
        bulk_price: Annotated[float, Form()],
        status: Annotated[Status, Form()]
        ):

    pricing_info = {
        "plant_type": plant_type,
        "packaging": packaging,
        "regular_price": regular_price,
        "bulk_price": bulk_price,
        "status": status
    }

    pricing_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id17,
        document_id=ID.unique(),
        data= pricing_info
    )

    return {
        "message": "Pricing information registered successfully",
        "pricing_id": pricing_create["$id"]
    }

@collection17_router.get("/pricing")
def get_all_pricing():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id17
        )
        # Extract the list of users
        pricing_users = result["documents"]

        return {
            "count": len(pricing_users),
            "users": pricing_users
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection17_router.get("/pricing/{pricing_id}")
def get_pricing_info(pricing_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id17,
            document_id= pricing_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection17_router.put("/pricing/{pricing_id}")
def update_pricing(
    pricing_id:str,
    plant_type:str,
    packaging: Annotated[str, Form()],
    regular_price: Annotated[float, Form()],
    bulk_price: Annotated[float, Form()],
    status: Annotated[float, Form()]):
    
    try:
        # Perform update
        updated_threshold_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id17,
            document_id=pricing_id,
            data={"plant_type": plant_type,
                  "packaging": packaging,
                  "regular_price": regular_price,
                  "bulk_price": bulk_price,
                  "status": status
            },
            permissions=[]
        )
        return {"message": "Threshold info updated successfully", "user": updated_threshold_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection17_router.delete("/pricing/{pricing_id}")
def delete_threshold(pricing_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id17, 
            document_id=pricing_id)
        return {"message": f"User with ID {pricing_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))