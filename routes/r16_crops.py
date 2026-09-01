from fastapi import APIRouter, Form, File, UploadFile, HTTPException, status
from typing import Annotated
from enum import Enum
import re
from main import db_id, db_collection_id16, client, bucket_id, project_id, appwrite_endpoint
from db import db
from appwrite.id import ID
from appwrite.input_file import InputFile
from storage import st
from audit_utils import write_audit


collection16_router = APIRouter(tags=["Crops"])


class PlantDurationUnit(str, Enum):
    DAYS = "days"
    MONTHS = "months"


def _parse_legacy_duration(value) -> tuple[int | None, str | None]:
    if isinstance(value, int) and value > 0:
        return value, PlantDurationUnit.DAYS.value
    text = str(value or "").strip().lower()
    match = re.search(r"(\d+)\s*(day|days|month|months|week|weeks)?", text)
    if not match:
        return None, None
    amount = int(match.group(1))
    if amount <= 0:
        return None, None
    unit = match.group(2) or "days"
    if unit.startswith("week"):
        return amount * 7, PlantDurationUnit.DAYS.value
    if unit.startswith("month"):
        return amount, PlantDurationUnit.MONTHS.value
    return amount, PlantDurationUnit.DAYS.value


def _resolve_duration(doc: dict) -> dict:
    value = doc.get("plant_duration_value")
    unit = str(doc.get("plant_duration_unit") or "").strip().lower()
    if isinstance(value, int) and value > 0 and unit in {"days", "months"}:
        return doc
    legacy_value, legacy_unit = _parse_legacy_duration(doc.get("plant_duration"))
    if legacy_value is not None and legacy_unit is not None:
        doc["plant_duration_value"] = legacy_value
        doc["plant_duration_unit"] = legacy_unit
    return doc


def _storage_view_url(file_id: str) -> str:
    return f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"


def _storage_download_url(file_id: str) -> str:
    return f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"


def _resolve_image_urls(doc: dict) -> dict:
    _resolve_duration(doc)
    if doc.get("crop_image_url"):
        return doc

    file_id = doc.get("crop_image_file_id")
    if not file_id and doc.get("crop_image"):
        try:
            files = st.list_files(bucket_id=bucket_id).get("files", [])
            for file in files:
                if file.get("name") == doc.get("crop_image"):
                    file_id = file.get("$id")
                    break
        except Exception:
            file_id = None

    if file_id:
        doc["crop_image_file_id"] = file_id
        doc["crop_image_url"] = _storage_view_url(file_id)
        doc["crop_image_download_url"] = _storage_download_url(file_id)
    return doc
   
@collection16_router.post("/crops/info")
async def register_crops_info(
    crop_image: Annotated[UploadFile, File(...)],
    crop_name: Annotated[str, Form()],
    variety_name: Annotated[str, Form()],
    plant_duration_value: Annotated[int, Form()],
    plant_duration_unit: Annotated[PlantDurationUnit, Form()],
    harvesting_weight: Annotated[float, Form()],
    company: Annotated[str, Form()],
    sprouting_ratio: Annotated[float, Form()],
    ec_level_min: Annotated[float, Form()],
    ec_level_max: Annotated[float, Form()],
    ph_level_min: Annotated[float, Form()],
    ph_level_max: Annotated[float, Form()],
    temp_min: Annotated[float, Form()],
    temp_max: Annotated[float, Form()],
    humidity_min: Annotated[float, Form()],
    humidity_max: Annotated[float, Form()],
    created_by: Annotated[str, Form(...)]
):
    if plant_duration_value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Plant duration must be greater than zero",
        )
    file_bytes = await crop_image.read()
    
    try:
        # Upload file to Appwrite Storage
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=crop_image.filename)
            # file=crop_image.file  # use the file object directly
        )
        file_id = uploaded_file["$id"]

        # Generate file URLs
        view_url = _storage_view_url(file_id)
        download_url = _storage_download_url(file_id)

        crop_data = {
            "crop_image": crop_image.filename,
            "crop_image_file_id": file_id,
            "crop_image_url": view_url,
            "crop_image_download_url": download_url,
            "crop_name": crop_name,
            "variety_name": variety_name,
            "plant_duration_value": plant_duration_value,
            "plant_duration_unit": plant_duration_unit.value,
            "harvesting_weight": harvesting_weight,
            "company": company,
            "sprouting_ratio": sprouting_ratio,
            "ec_level_min": ec_level_min,
            "ec_level_max": ec_level_max,
            "ph_level_min": ph_level_min,
            "ph_level_max": ph_level_max,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "humidity_min": humidity_min,
            "humidity_max": humidity_max,
            "created_by": created_by
        }

        try:
            saved_doc = db.create_document(
                database_id=db_id,
                collection_id=db_collection_id16,
                document_id=ID.unique(),
                data=crop_data
            )
        except Exception:
            crop_data.pop("crop_image_file_id", None)
            crop_data.pop("crop_image_url", None)
            crop_data.pop("crop_image_download_url", None)
            saved_doc = db.create_document(
                database_id=db_id,
                collection_id=db_collection_id16,
                document_id=ID.unique(),
                data=crop_data
            )
        write_audit(
            action_type="Create",
            collection_name="Crops",
            performed_by_id=created_by,
            action_details=f"Created crop variety {crop_name} - {variety_name}",
            new_data=crop_data
        )

        return {
            "message": "File created successfully",
            "file_id": file_id,
            "view_url": view_url,
            "download_url": download_url,
            "db_document_id": saved_doc["$id"]
        }

    except Exception as e:
        return {"error": str(e)}

@collection16_router.get("/crops")
def get_all_crops():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id16
        )

        # Extract the list of users
        crop_users = [_resolve_image_urls(dict(doc)) for doc in result["documents"]]

        return {
            "count": len(crop_users),
            "users": crop_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection16_router.get("/crops/{crops_id}")
def get_crop_info(sensors_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id16,
            document_id= sensors_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")

@collection16_router.put("/crops/info/{document_id}")
async def update_crops_info(
    document_id: str,
    crop_image: Annotated[UploadFile, File(...)]= None,
    crop_name: Annotated[str, Form()]= None,
    variety_name: Annotated[str, Form()]= None,
    plant_duration_value: Annotated[int, Form()]= None,
    plant_duration_unit: Annotated[PlantDurationUnit, Form()]= None,
    harvesting_weight: Annotated[float, Form()] = None,
    company: Annotated[str, Form()] = None,
    sprouting_ratio: Annotated[float, Form()]= None,
    ec_level_min: Annotated[float, Form()]= None,
    ec_level_max: Annotated[float, Form()]= None,
    ph_level_min: Annotated[float, Form()]= None,
    ph_level_max: Annotated[float, Form()]= None,
    temp_min: Annotated[float, Form()]= None,
    temp_max: Annotated[float, Form()] = None,
    humidity_min: Annotated[float, Form()]= None,
    humidity_max: Annotated[float, Form()]= None,
    created_by: Annotated[str, Form(...)]= None
):
    if plant_duration_value is not None and plant_duration_value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Plant duration must be greater than zero",
        )
    if (plant_duration_value is None) != (plant_duration_unit is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Plant duration value and unit must be updated together",
        )
    update_data = {}
    view_url = None
    download_url = None

    # If a new image is uploaded, replace the old one
    if crop_image:
        file_bytes = await crop_image.read()
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=crop_image.filename)
        )

        file_id = uploaded_file["$id"]
        view_url = _storage_view_url(file_id)
        download_url = _storage_download_url(file_id)

        update_data["crop_image_file_id"] = file_id
        update_data["crop_image_url"] = view_url
        update_data["crop_image_download_url"] = download_url

    # Only include fields that were actually provided
    form_fields = {
        "crop_name": crop_name,
        "variety_name": variety_name,
        "plant_duration_value": plant_duration_value,
        "plant_duration_unit": (
            plant_duration_unit.value if plant_duration_unit is not None else None
        ),
        "harvesting_weight": harvesting_weight,
        "company": company,
        "sprouting_ratio": sprouting_ratio,
        "ec_level_min": ec_level_min,
        "ec_level_max": ec_level_max,
        "ph_level_min": ph_level_min,
        "ph_level_max": ph_level_max,
        "temp_min": temp_min,
        "temp_max": temp_max,
        "humidity_min": humidity_min,
        "humidity_max": humidity_max,
        "created_by": created_by
    }
    if crop_image:
        form_fields["crop_image"] = crop_image.filename

    # Add only non-None fields to the update payload
    for key, value in form_fields.items():
        if value is not None:
            update_data[key] = value

    try:
        previous_crop = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id16,
            document_id=document_id
        )
        # Update the existing document in Appwrite Database
        updated_doc = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id16,
            document_id=document_id,
            data=update_data
        )
        write_audit(
            action_type="Update",
            collection_name="Crops",
            performed_by_id=created_by or previous_crop.get("created_by", "system"),
            action_details=f"Updated crop variety {update_data.get('crop_name', previous_crop.get('crop_name', document_id))}",
            previous_data=previous_crop,
            new_data=update_data
        )

        return {
            "message": "Crop info updated successfully",
            "document_id": updated_doc["$id"],
            "updated_fields": update_data,
            "view_url": view_url,
            "download_url": download_url,
        }

    except Exception as e:
        return {"error": str(e)}

@collection16_router.delete("/crops/{crops_id}")
def delete_crop(crops_id:str):
    try:
        previous_crop = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id16,
            document_id=crops_id
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id16, 
            document_id=crops_id)
        write_audit(
            action_type="Delete",
            collection_name="Crops",
            performed_by_id=previous_crop.get("created_by", "system"),
            action_details=f"Deleted crop variety {previous_crop.get('crop_name', crops_id)}",
            previous_data=previous_crop
        )
        return {"message": f"User with ID {crops_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
