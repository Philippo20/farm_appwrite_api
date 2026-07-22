from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id9
from db import db
from appwrite.id import ID
from audit_utils import write_audit

collection9_router = APIRouter(tags=["Package"])

class Status(str, Enum):
    ACTIVE = "Active"
    DAMAGE = "Damaged"
    OUT_OF_STOCK= "Out_of_stock"
    ARCHIVED= "Archived"

@collection9_router.post("/package/info")
def register_package(
        package_name: Annotated[str, Form()],
        plant_type_id: Annotated[str, Form()],
        plant_type_name: Annotated[str, Form()],
        material_used: Annotated[str, Form()],
        weight_capacity: Annotated[float, Form()],
        unit: Annotated[str, Form()],
        quantity_available: Annotated[float, Form()],
        cost_per_unit: Annotated[float, Form()],
        created_by: Annotated[str, Form()],
        created_at: Annotated[datetime, Form(...)],
        updated_at: Annotated[datetime, Form(...)],
        status: Annotated[Status, Form()]
        ):
    package_info = {
        "package_id": ID.unique(),
        "package_name": package_name,
        "plant_type_id": plant_type_id,
        "plant_type_name": plant_type_name,
        "material_used": material_used,
        "weight_capacity": weight_capacity,
        "unit": unit,
        "quantity_available": quantity_available,
        "cost_per_unit": cost_per_unit,
        "created_by": created_by,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
        "status": status
    }
    print(package_info)

    package_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id9,
        document_id=ID.unique(),
        data= package_info
    )
    write_audit(
        action_type="Create",
        collection_name="Package",
        performed_by_id=created_by,
        action_details=f"Created package {package_name}",
        new_data=package_info
    )

    return {
        "message": "User registered successfully",
        "package_id": package_create["$id"]
    }

@collection9_router.get("/package")
def get_all_package_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id9
        )

        # Extract the list of users
        package_users = result["documents"]

        return {
            "count": len(package_users),
            "users": package_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection9_router.get("/package/{package_id}")
def get_package_info(package_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id9,
            document_id= package_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection9_router.put("/package/{package_id}")
def update_package(package_id:str,
    package_name: Annotated[str, Form()],
    plant_type_id: Annotated[str, Form()],
    plant_type_name: Annotated[str, Form()],
    material_used: Annotated[str, Form()],
    weight_capacity: Annotated[float, Form()],
    unit: Annotated[str, Form()],
    quantity_available: Annotated[float, Form()],
    cost_per_unit: Annotated[float, Form()],
    created_by: Annotated[str, Form()],
    created_at: Annotated[datetime, Form(...)],
    updated_at: Annotated[datetime, Form(...)],
    status: Annotated[Status, Form()]
    ):
    try:
        previous_package = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id9,
            document_id=package_id
        )
        update_data = {
                  "package_name": package_name,
                  "plant_type_id": plant_type_id,
                  "plant_type_name": plant_type_name,
                  "material_used": material_used,
                  "weight_capacity": weight_capacity,
                  "unit": unit,
                  "quantity_available": quantity_available,
                  "cost_per_unit": cost_per_unit,
                  "created_by": created_by,
                  "created_at": created_at.isoformat(),
                  "updated_at": updated_at.isoformat(),
                  "status": status
            }
        # Perform update
        updated_package_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id9,
            document_id=package_id,
            data=update_data,
            permissions=[]
        )
        write_audit(
            action_type="Update",
            collection_name="Package",
            performed_by_id=created_by,
            action_details=f"Updated package {package_name}",
            previous_data=previous_package,
            new_data=update_data
        )
        return {"message": "Package info updated successfully", "user": updated_package_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection9_router.delete("/package/{package_id}")
def delete_package(package_id:str):
    try:
        previous_package = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id9,
            document_id=package_id
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id9, 
            document_id=package_id)
        write_audit(
            action_type="Delete",
            collection_name="Package",
            performed_by_id=previous_package.get("created_by", "system"),
            action_details=f"Deleted package {previous_package.get('package_name', package_id)}",
            previous_data=previous_package
        )
        return {"message": f"User with ID {package_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
