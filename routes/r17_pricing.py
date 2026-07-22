from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from main import db_id, db_collection_id17
from db import db
from appwrite.id import ID
from appwrite.query import Query
from audit_utils import write_audit

collection17_router = APIRouter(tags=["Pricing"])

class Status(str, Enum):
    ACTIVE = "Active"
    REVIEW = "Review"
    INACTIVE = "Inactive"

class PricingType(str, Enum):
    HUB_PURCHASE = "hub_purchase"
    HUB_SALE = "hub_sale"

@collection17_router.post("/pricing/info")
def register_pricing_info(
        plant_type: Annotated[str, Form()],
        regular_price: Annotated[float, Form()],
        bulk_price: Annotated[float, Form()],
        status: Annotated[Status, Form()],
        pricing_type: Annotated[PricingType, Form()] = PricingType.HUB_PURCHASE,
        farm_id: Annotated[str, Form()] = "all",
        farm_name: Annotated[str, Form()] = "Hub Pricing",
        crop_variety: Annotated[str, Form()] = "",
        packaging: Annotated[str, Form()] = "Raw / Unpackaged",
        unit: Annotated[str, Form()] = "kg"
        ):
    if pricing_type == PricingType.HUB_PURCHASE:
        packaging = "Raw / Unpackaged"
        if not farm_id or farm_id == "all":
            raise HTTPException(
                status_code=400,
                detail="Hub purchase pricing requires a spoke farm."
            )
    elif pricing_type == PricingType.HUB_SALE:
        farm_id = "all"
        farm_name = "Hub Sales"
        if not packaging or packaging == "Raw / Unpackaged":
            raise HTTPException(
                status_code=400,
                detail="Hub sale pricing requires a packaging option."
            )

    pricing_info = {
        "pricing_type": pricing_type.value,
        "farm_id": farm_id,
        "farm_name": farm_name,
        "plant_type": plant_type,
        "crop_variety": crop_variety,
        "packaging": packaging,
        "unit": unit,
        "regular_price": regular_price,
        "bulk_price": bulk_price,
        "status": status.value
    }

    pricing_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id17,
        document_id=ID.unique(),
        data= pricing_info
    )
    write_audit(
        action_type="Create",
        collection_name="Pricing",
        action_details=f"Created {pricing_type.value} pricing for {plant_type}",
        new_data=pricing_info
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
    plant_type: Annotated[str, Form()],
    regular_price: Annotated[float, Form()],
    bulk_price: Annotated[float, Form()],
    status: Annotated[Status, Form()],
    pricing_type: Annotated[PricingType, Form()] = PricingType.HUB_PURCHASE,
    farm_id: Annotated[str, Form()] = "all",
    farm_name: Annotated[str, Form()] = "Hub Pricing",
    crop_variety: Annotated[str, Form()] = "",
    packaging: Annotated[str, Form()] = "Raw / Unpackaged",
    unit: Annotated[str, Form()] = "kg"):
    if pricing_type == PricingType.HUB_PURCHASE:
        packaging = "Raw / Unpackaged"
        if not farm_id or farm_id == "all":
            raise HTTPException(
                status_code=400,
                detail="Hub purchase pricing requires a spoke farm."
            )
    elif pricing_type == PricingType.HUB_SALE:
        farm_id = "all"
        farm_name = "Hub Sales"
        if not packaging or packaging == "Raw / Unpackaged":
            raise HTTPException(
                status_code=400,
                detail="Hub sale pricing requires a packaging option."
            )
    
    try:
        previous_pricing = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id17,
            document_id=pricing_id
        )
        update_data = {"pricing_type": pricing_type.value,
                  "farm_id": farm_id,
                  "farm_name": farm_name,
                  "plant_type": plant_type,
                  "crop_variety": crop_variety,
                  "packaging": packaging,
                  "unit": unit,
                  "regular_price": regular_price,
                  "bulk_price": bulk_price,
                  "status": status.value
            }
        # Perform update
        updated_threshold_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id17,
            document_id=pricing_id,
            data=update_data,
            permissions=[]
        )
        write_audit(
            action_type="Update",
            collection_name="Pricing",
            action_details=f"Updated {pricing_type.value} pricing for {plant_type}",
            previous_data=previous_pricing,
            new_data=update_data
        )
        return {"message": "Pricing info updated successfully", "user": updated_threshold_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection17_router.delete("/pricing/{pricing_id}")
def delete_threshold(pricing_id:str):
    try:
        previous_pricing = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id17,
            document_id=pricing_id
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id17, 
            document_id=pricing_id)
        write_audit(
            action_type="Delete",
            collection_name="Pricing",
            action_details=f"Deleted pricing for {previous_pricing.get('plant_type', pricing_id)}",
            previous_data=previous_pricing
        )
        return {"message": f"Pricing with ID {pricing_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
