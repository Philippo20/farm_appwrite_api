from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from main import db_id, db_collection_id3
from db import db
from appwrite.id import ID
from audit_utils import write_audit
import math


collection3_router = APIRouter(tags=["Plant type"])

class Status(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class MaturityUnit(str, Enum):
    WEEKS = "weeks"
    MONTHS = "months"

def _maturity_fields(min_value: int, max_value: int, unit: MaturityUnit):
    if min_value <= 0 or max_value < min_value:
        raise HTTPException(status_code=400, detail="Maturity range is invalid")
    if unit == MaturityUnit.MONTHS:
        min_weeks = max(1, math.ceil(min_value * 4.345))
        max_weeks = max(min_weeks, math.ceil(max_value * 4.345))
    else:
        min_weeks, max_weeks = min_value, max_value
    return {
        "maturity_min_weeks": min_weeks,
        "maturity_max_weeks": max_weeks,
        "maturity_unit": unit.value,
        "maturity_min_value": min_value,
        "maturity_max_value": max_value,
    }

@collection3_router.post("/plant_type/info")
async def register_plant_type(
        name: Annotated[str, Form()],
        image_url: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        months_to_maturity: Annotated[int | None, Form()] = None,
        maturity_min_value: Annotated[int | None, Form()] = None,
        maturity_max_value: Annotated[int | None, Form()] = None,
        maturity_unit: Annotated[MaturityUnit | None, Form()] = None,
        category: Annotated[str, Form()] = "Plant Types",
        ):
    try:
        plant_data = {
                "name": name,
                "category": category,
                "is_category": False,
                "farmID": "plant-catalog",
                "image_url": image_url,
                "growth_conditions": "Moved to crop/production settings",
                "packaging_weights": 0,
                "package_types": "Medium",
                "price_per_package": 0,
                "status": status,
                "created_by": "Plant Type Catalog"
                }
        min_value = maturity_min_value or months_to_maturity or 1
        max_value = maturity_max_value or months_to_maturity or min_value
        plant_data.update(_maturity_fields(
            min_value, max_value, maturity_unit or MaturityUnit.MONTHS))
        plant_type_info_doc = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=ID.unique(),
            data=plant_data
        )
        write_audit(
            action_type="Create",
            collection_name="Plant types",
            action_details=f"Created plant type {name}",
            new_data=plant_data
        )
        return {
            "message": "Plant-type details are successfully created",
            "plant_type_ID": plant_type_info_doc["$id"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@collection3_router.get("/plant_type")
def get_all_plant_type_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id3
        )

        # Extract the list of users
        plant_type_users = result["documents"]

        return {
            "count": len(plant_type_users),
            "users": plant_type_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@collection3_router.post("/plant_type/categories")
async def create_plant_type_category(
        name: Annotated[str, Form()],
        status: Annotated[Status, Form()] = Status.ACTIVE,
        ):
    category = name.strip()
    if not category:
        raise HTTPException(status_code=400, detail="Category name is required")
    try:
        existing = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id3
        )["documents"]
        for doc in existing:
            if doc.get("is_category") and doc.get("category", "").lower() == category.lower():
                return {
                    "message": "Category already exists",
                    "category_id": doc["$id"]
                }

        category_data = {
                "name": category,
                "category": category,
                "is_category": True,
                "farmID": "plant-category",
                "image_url": "",
                "growth_conditions": "Category marker",
                "packaging_weights": 0,
                "package_types": "Medium",
                "price_per_package": 0,
                "status": status,
                "created_by": "Plant Type Catalog"
            }
        category_doc = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=ID.unique(),
            data=category_data
        )
        write_audit(
            action_type="Create",
            collection_name="Plant types",
            action_details=f"Created plant type category {category}",
            new_data=category_data
        )
        return {
            "message": "Plant type category created",
            "category_id": category_doc["$id"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@collection3_router.delete("/plant_type/categories/{category_id}")
def delete_plant_type_category(category_id: str):
    try:
        category_doc = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=category_id
        )
        if not category_doc.get("is_category"):
            raise HTTPException(status_code=400, detail="Document is not a category")
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=category_id
        )
        write_audit(
            action_type="Delete",
            collection_name="Plant types",
            action_details=f"Deleted plant type category {category_doc.get('name', category_id)}",
            previous_data=category_doc
        )
        return {"message": "Plant type category deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection3_router.get("/plant_type/{plant_type_id}")
def get_plant_type_info(plant_type_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id3,
            document_id= plant_type_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection3_router.put("/plant_type/{plant_type_id}")
async def update_plant_type(plant_type_id:str,
    name: Annotated[str, Form()],
    image_url: Annotated[str, Form()],
    status: Annotated[Status, Form()],
    months_to_maturity: Annotated[int | None, Form()] = None,
    maturity_min_value: Annotated[int | None, Form()] = None,
    maturity_max_value: Annotated[int | None, Form()] = None,
    maturity_unit: Annotated[MaturityUnit | None, Form()] = None,
    category: Annotated[str, Form()] = "Plant Types"
    ):
    try:
        previous_doc = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=plant_type_id
        )
        update_data = {
                "name": name,
                "category": category,
                "is_category": False,
                "image_url": image_url,
                "status": status,
            }
        min_value = maturity_min_value or months_to_maturity or 1
        max_value = maturity_max_value or months_to_maturity or min_value
        update_data.update(_maturity_fields(
            min_value, max_value, maturity_unit or MaturityUnit.MONTHS))
        updated_doc = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=plant_type_id,
            data=update_data
        )
        write_audit(
            action_type="Update",
            collection_name="Plant types",
            action_details=f"Updated plant type {name}",
            previous_data=previous_doc,
            new_data=update_data
        )

        return {
            "message": "Plant type updated successfully",
            "document_id": updated_doc["$id"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection3_router.delete("/plant_type/{plant_type_id}")
def delete_plant_type(plant_type_id:str):
    try:
        previous_doc = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=plant_type_id
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id3, 
            document_id=plant_type_id)
        write_audit(
            action_type="Delete",
            collection_name="Plant types",
            action_details=f"Deleted plant type {previous_doc.get('name', plant_type_id)}",
            previous_data=previous_doc
        )
        return {"message": f"Plant type with ID {plant_type_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
