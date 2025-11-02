from fastapi import APIRouter, Form, File, UploadFile, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date, timezone
from main import db_id, db_collection_id3, bucket_id, project_id, appwrite_endpoint
from db import db
from appwrite.id import ID
from appwrite.query import Query
from appwrite.input_file import InputFile
from storage import st


collection3_router = APIRouter(tags=["Plant type"])

@collection3_router.post("/plant_type/info")
async def register_plant_type(
        name: Annotated[str, Form()],
        farmID: Annotated[str, Form()],
        days_to_maturity: Annotated[int, Form()],
        image_url: Annotated[UploadFile, Form()],
        growth_conditions: Annotated[str, Form()],
        packaging_weights: Annotated[float, Form()],
        package_types: Annotated[str, Form()],
        price_per_package: Annotated[float, Form()],
        created_by: Annotated[str, Form()],
        created_at: Annotated[date, Form(...)],
        updated_at: Annotated[datetime, Form(...)]
        ):
    updated_at = datetime.now(timezone.utc).isoformat()
    
    file_bytes = await image_url.read()
    
    try:
        # Upload file to Appwrite Storage
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=image_url.filename)
            # file=crop_image.file  # use the file object directly
        )
        file_id = uploaded_file["$id"]

        # Generate file URLs
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"


        # Save URLs to Appwrite Database
        plant_type_info_doc = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=ID.unique(),
            data={
                "name": name,
                "farmID": farmID,
                "days_to_maturity": days_to_maturity,
                "image_url": image_url.filename,
                "growth_conditions": growth_conditions,
                "packaging_weights": packaging_weights,
                "package_types": package_types,
                "price_per_package": price_per_package,
                "created_by": created_by,
                "created_at": created_at.isoformat(),
                "updated_at": updated_at
                }
        )
        return {
            "message": "Plant-type details are successfully created",
            "file_id": file_id,
            "view_url": view_url,
            "download_url": download_url,
            "plant_type_ID": plant_type_info_doc["$id"]
        }
    except Exception as e:
        return {"error": str(e)}

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
    farmID: Annotated[str, Form()],
    days_to_maturity: Annotated[int, Form()],
    image_url: Annotated[UploadFile, Form()],
    growth_conditions: Annotated[str, Form()],
    packaging_weights: Annotated[float, Form()],
    package_types: Annotated[str, Form()],
    price_per_package: Annotated[float, Form()],
    created_by: Annotated[str, Form()],
    created_at: Annotated[date, Form(...)],
    updated_at: Annotated[datetime, Form(...)]
    ):
    updated_at = datetime.now(timezone.utc).isoformat()

    update_data = {}

    # If a new image is uploaded, replace the old one
    if image_url:
        file_bytes = await image_url.read()
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=image_url.filename)
        )

        file_id = uploaded_file["$id"]
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"

    # Only include fields that were actually provided
    form_fields = {"name": name,
                  "farmID": farmID,
                  "days_to_maturity": days_to_maturity,
                  "image_url": image_url,
                  "growth_conditions": growth_conditions,
                  "packaging_weights": packaging_weights,
                  "package_types": package_types,
                  "price_per_package": price_per_package,
                  "created_by": created_by,
                  "created_at": created_at.isoformat(),
                  "updated_at": updated_at
            }
            # permissions=[]
    # Add only non-None fields to the update payload
    for key, value in form_fields.items():
        if value is not None:
            update_data[key] = value

    try:
        # Update the existing document in Appwrite Database
        updated_doc = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id3,
            document_id=plant_type_id,
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
    
@collection3_router.delete("/plant_type/{plant_type_id}")
def delete_plant_type(plant_type_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id3, 
            document_id=plant_type_id)
        return {"message": f"User with ID {plant_type_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))