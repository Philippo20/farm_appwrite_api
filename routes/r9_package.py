from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id9, db_collection_id16
from db import db
from appwrite.id import ID
from audit_utils import write_audit

collection9_router = APIRouter(tags=["Package"])

class Status(str, Enum):
    ACTIVE = "Active"
    DAMAGE = "Damaged"
    OUT_OF_STOCK= "Out_of_stock"
    ARCHIVED= "Archived"


def _resolve_crop_variety(crop_variety_id: str):
    try:
        variety = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id16,
            document_id=crop_variety_id,
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a valid crop variety for this packaging configuration.",
        ) from error
    if not str(variety.get("variety_name") or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected crop record does not contain a variety name.",
        )
    return variety


def _validate_package_numbers(weight_capacity, quantity_available, cost_per_unit):
    if weight_capacity <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Product capacity must be greater than zero.",
        )
    if quantity_available < 0 or cost_per_unit < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stock and package cost cannot be negative.",
        )

@collection9_router.post("/package/info")
def register_package(
        package_name: Annotated[str, Form()],
        crop_variety_id: Annotated[str, Form()],
        crop_variety_name: Annotated[str, Form()],
        crop_name: Annotated[str, Form()],
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
    variety = _resolve_crop_variety(crop_variety_id)
    _validate_package_numbers(weight_capacity, quantity_available, cost_per_unit)
    resolved_variety_name = str(variety.get("variety_name") or crop_variety_name).strip()
    resolved_crop_name = str(variety.get("crop_name") or crop_name).strip()
    package_info = {
        "package_id": ID.unique(),
        "package_name": package_name,
        "crop_variety_id": crop_variety_id,
        "crop_variety_name": resolved_variety_name,
        "crop_name": resolved_crop_name,
        "plant_type_id": crop_variety_id,
        "plant_type_name": resolved_crop_name,
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
        "message": "Packaging configuration created successfully",
        "package_id": package_create["$id"]
    }

@collection9_router.get("/package")
def get_all_package_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id9
        )
        package_users = result["documents"]
        legacy_packages = [
            package
            for package in package_users
            if not str(package.get("crop_variety_id") or "").strip()
        ]
        if legacy_packages:
            varieties = db.list_documents(
                database_id=db_id,
                collection_id=db_collection_id16,
            ).get("documents", [])
            varieties_by_crop = {}
            for variety in varieties:
                crop_key = str(variety.get("crop_name") or "").strip().casefold()
                if crop_key:
                    varieties_by_crop.setdefault(crop_key, []).append(variety)

            for package in legacy_packages:
                crop_key = str(package.get("plant_type_name") or "").strip().casefold()
                matches = varieties_by_crop.get(crop_key, [])
                if len(matches) != 1:
                    continue
                variety = matches[0]
                migration_data = {
                    "crop_variety_id": str(variety.get("$id") or ""),
                    "crop_variety_name": str(variety.get("variety_name") or "").strip(),
                    "crop_name": str(variety.get("crop_name") or "").strip(),
                }
                try:
                    db.update_document(
                        database_id=db_id,
                        collection_id=db_collection_id9,
                        document_id=package["$id"],
                        data=migration_data,
                    )
                    package.update(migration_data)
                except Exception:
                    # The catalog still returns the legacy row so an admin can
                    # assign its exact variety manually.
                    pass

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
    crop_variety_id: Annotated[str, Form()],
    crop_variety_name: Annotated[str, Form()],
    crop_name: Annotated[str, Form()],
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
        variety = _resolve_crop_variety(crop_variety_id)
        _validate_package_numbers(weight_capacity, quantity_available, cost_per_unit)
        resolved_variety_name = str(variety.get("variety_name") or crop_variety_name).strip()
        resolved_crop_name = str(variety.get("crop_name") or crop_name).strip()
        previous_package = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id9,
            document_id=package_id
        )
        update_data = {
                  "package_name": package_name,
                  "crop_variety_id": crop_variety_id,
                  "crop_variety_name": resolved_variety_name,
                  "crop_name": resolved_crop_name,
                  "plant_type_id": crop_variety_id,
                  "plant_type_name": resolved_crop_name,
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

    except HTTPException:
        raise
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
