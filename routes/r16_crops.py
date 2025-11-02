from fastapi import APIRouter, Form, File, UploadFile, HTTPException, status
from pydantic import BaseModel
from typing import Annotated
from main import db_id, db_collection_id16, client, bucket_id, project_id, appwrite_endpoint
from db import db
from appwrite.id import ID
from appwrite.input_file import InputFile
from storage import st


collection16_router = APIRouter(tags=["Crops"])
   
@collection16_router.post("/crops/info")
async def register_crops_info(
    crop_image: Annotated[UploadFile, File(...)],
    crop_name: Annotated[str, Form()],
    variety_name: Annotated[str, Form()],
    plant_duration: Annotated[str, Form()],
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
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"

        # Save URLs to Appwrite Database
        saved_doc = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id16,
            document_id=ID.unique(),
            data={
                "crop_image": crop_image.filename,
                "crop_name": crop_name,
                "variety_name": variety_name,
                "plant_duration": plant_duration,
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
        crop_users = result["documents"]

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
    plant_duration: Annotated[str, Form()]= None,
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
    update_data = {}

    # If a new image is uploaded, replace the old one
    if crop_image:
        file_bytes = await crop_image.read()
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=crop_image.filename)
        )

        file_id = uploaded_file["$id"]
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"

        # update_data["crop_image"] = view_url
        # update_data["download_url"] = download_url

    # Only include fields that were actually provided
    form_fields = {
        "crop_image": crop_image.filename,
        "crop_name": crop_name,
        "variety_name": variety_name,
        "plant_duration": plant_duration,
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

    # Add only non-None fields to the update payload
    for key, value in form_fields.items():
        if value is not None:
            update_data[key] = value

    try:
        # Update the existing document in Appwrite Database
        updated_doc = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id16,
            document_id=document_id,
            data=update_data
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
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id16, 
            document_id=crops_id)
        return {"message": f"User with ID {crops_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))