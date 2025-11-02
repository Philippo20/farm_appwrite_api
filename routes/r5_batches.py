from fastapi import APIRouter, Form, File, UploadFile, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date, timezone
from main import db_id, db_collection_id5, bucket_id, project_id, appwrite_endpoint
from db import db
from appwrite.id import ID
from appwrite.query import Query
from appwrite.input_file import InputFile
from storage import st


collection5_router = APIRouter(tags=["Batches"])


class ProductionStatus(str, Enum):
    PLANTED = "Planted"
    GROWING = "Growing"
    HARVESTED = "Harvested"
    DELIVERED = "Delivered"
    COMPLETED = "Completed"

class FinancialStatus(str, Enum):
    PENDING = "Pending"
    PARTIALLY_PAID = "Partially Paid"
    CLEARED = "Cleared"

class DeliveryStatus(str, Enum):
    PENDING = "Pending"
    IN_TRANSIT = "In Transit"
    DELIVERED = "Delivered"

@collection5_router.post("/batches/info")
async def register_batch(
        batch_no: Annotated[str, Form()],
        farmID: Annotated[str, Form()],
        farm_name: Annotated[str, Form()],
        plant_type_ID: Annotated[str, Form()],
        plant_name: Annotated[str, Form()],
        farm_manager_id: Annotated[str, Form()],
        farm_manager_name: Annotated[str, Form()],
        caretaker_id: Annotated[str, Form()],
        caretaker_name: Annotated[str, Form()],
        start_date: Annotated[date, Form(...)],
        actual_harvest_date: Annotated[date, Form(...)],
        total_seeds_nursed: Annotated[int, Form()],
        total_harvested: Annotated[int, Form()],
        total_transplanted: Annotated[int, Form()],
        total_weight_kg: Annotated[float, Form()],
        harvest_images: Annotated[UploadFile, Form()],
        production_status: Annotated[ProductionStatus, Form()],
        technical_issues: Annotated[str, Form()],
        inputs_supplied: Annotated[str, Form()],
        funds_requested: Annotated[str, Form()],
        financial_status: Annotated[FinancialStatus, Form()],
        fund_request_id: Annotated[str, Form()],
        delivery_status: Annotated[DeliveryStatus, Form()],
        delivery_details: Annotated[str, Form()],
        created_by: Annotated[str, Form()],
        created_at: Annotated[date, Form(...)],
        updated_at: Annotated[datetime, Form(...)],
        end_date: Annotated[date, Form(...)]= None,
        ):
    updated_at = datetime.now(timezone.utc).isoformat()
    
    file_bytes = await harvest_images.read()
    
    try:
        # Upload file to Appwrite Storage
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=harvest_images.filename)
            # file=crop_image.file  # use the file object directly
        )
        file_id = uploaded_file["$id"]

        # Generate file URLs
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"


        # Save URLs to Appwrite Database
        batches_info = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id5,
            document_id=ID.unique(),
            data={
                "batch_no": batch_no,
                "farmID": farmID,
                "farm_name": farm_name,
                "plant_type_ID": plant_type_ID,
                "plant_name": plant_name,
                "farm_manager_id": farm_manager_id,
                "farm_manager_name": farm_manager_name,
                "caretaker_id": caretaker_id,
                "caretaker_name": caretaker_name,   
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "actual_harvest_date": actual_harvest_date.isoformat(),
                "total_seeds_nursed": total_seeds_nursed,   
                "total_harvested": total_harvested,   
                "total_transplanted": total_transplanted,   
                "total_weight_kg": total_weight_kg,   
                "harvest_images": harvest_images,   
                "production_status": production_status,   
                "technical_issues": technical_issues,   
                "inputs_supplied": inputs_supplied,   
                "funds_requested": funds_requested,   
                "financial_status": financial_status,   
                "fund_request_id": fund_request_id,   
                "delivery_status": delivery_status,   
                "delivery_details": delivery_details,   
                "created_by": created_by,   
                "created_at": created_at.isoformat(),
                "updated_at": updated_at
            }
        )
        return {
            "message": "Batches information created successfully",
            "file_id": file_id,
            "view_url": view_url,
            "download_url": download_url,
            "batch_id": batches_info["$id"]
        }
    except Exception as e:
        return {"error": str(e)}

@collection5_router.get("/batches")
def get_all_batches_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id5
        )

        # Extract the list of users
        batches_users = result["documents"]

        return {
            "count": len(batches_users),
            "users": batches_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection5_router.get("/batches/{batch_no}")
def get_batch_info(batch_no:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id5,
            document_id= batch_no
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection5_router.put("/batches/{batch_no}")
async def update_batch(batch_id:str,
    batch_no: Annotated[str, Form()],
    farmID: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    plant_type_ID: Annotated[str, Form()],
    plant_name: Annotated[str, Form()],
    farm_manager_id: Annotated[str, Form()],
    farm_manager_name: Annotated[str, Form()],
    caretaker_id: Annotated[str, Form()],
    caretaker_name: Annotated[str, Form()],
    start_date: Annotated[date, Form(...)],
    actual_harvest_date: Annotated[date, Form(...)],
    total_seeds_nursed: Annotated[int, Form()],
    total_harvested: Annotated[int, Form()],
    total_transplanted: Annotated[int, Form()],
    total_weight_kg: Annotated[float, Form()],
    harvest_images: Annotated[UploadFile, Form()],
    production_status: Annotated[ProductionStatus, Form()],
    technical_issues: Annotated[str, Form()],
    inputs_supplied: Annotated[str, Form()],
    funds_requested: Annotated[str, Form()],
    financial_status: Annotated[FinancialStatus, Form()],
    fund_request_id: Annotated[str, Form()],
    delivery_status: Annotated[DeliveryStatus, Form()],
    delivery_details: Annotated[str, Form()],
    created_by: Annotated[str, Form()],
    created_at: Annotated[date, Form(...)],
    updated_at: Annotated[datetime, Form(...)],
    end_date: Annotated[date, Form(...)]= None,
    ):
    updated_at = datetime.now(timezone.utc).isoformat()

    update_data = {}

    # If a new image is uploaded, replace the old one
    if harvest_images:
        file_bytes = await harvest_images.read()
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=harvest_images.filename)
        )

        file_id = uploaded_file["$id"]
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"

    # Only include fields that were actually provided
    form_fields = {"batch_no": batch_no,
                  "farmID": farmID,
                  "farm_name": farm_name,
                  "plant_type_ID": plant_type_ID,
                  "plant_name": plant_name,
                  "farm_manager_id": farm_manager_id,
                  "farm_manager_name": farm_manager_name,
                  "caretaker_id": caretaker_id,
                  "caretaker_name": caretaker_name,   
                  "start_date": start_date.isoformat(),
                  "end_date": end_date.isoformat(),
                  "actual_harvest_date": actual_harvest_date.isoformat(),
                  "total_seeds_nursed": total_seeds_nursed,   
                  "total_harvested": total_harvested,   
                  "total_transplanted": total_transplanted,   
                  "total_weight_kg": total_weight_kg,   
                  "harvest_images": harvest_images,   
                  "production_status": production_status,   
                  "technical_issues": technical_issues,   
                  "inputs_supplied": inputs_supplied,   
                  "funds_requested": funds_requested,   
                  "financial_status": financial_status,   
                  "fund_request_id": fund_request_id,   
                  "delivery_status": delivery_status,   
                  "delivery_details": delivery_details,   
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
            collection_id=db_collection_id5,
            document_id=batch_id,
            data=update_data
        )

        return {
            "message": "Crop info updated successfully",
            "document_id": updated_doc["$id"],
            "updated_batches": update_data,
            "view_url": view_url,
            "download_url": download_url,
        }

    except Exception as e:
        return {"error": str(e)}

@collection5_router.delete("/batches/{batch_no}")
def delete_batch(batch_no:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id5, 
            document_id=batch_no)
        return {"message": f"User with ID {batch_no} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))