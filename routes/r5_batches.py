from fastapi import APIRouter, Form, File, UploadFile, HTTPException, status
from typing import Annotated, Optional
from enum import Enum
from datetime import datetime, date, timezone
from main import (
    db_id,
    db_collection_id1,
    db_collection_id2,
    db_collection_id3,
    db_collection_id5,
    bucket_id,
    project_id,
    appwrite_endpoint,
)
from db import db
from appwrite.id import ID
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
        batch_no: Annotated[str, Form(...)],
        farmID: Annotated[str, Form(...)],
        farm_name: Annotated[str, Form(...)],
        plant_type_ID: Annotated[str, Form(...)],
        plant_name: Annotated[str, Form(...)],
        plant_variety: Annotated[str, Form(...)],
        farm_manager_id: Annotated[str, Form(...)],
        farm_manager_name: Annotated[str, Form(...)],
        start_date: Annotated[date, Form(...)],
        end_date: Annotated[date, Form(...)],
        total_seeds_nursed: Annotated[int, Form(...)],
        created_by: Annotated[str, Form()],
        technical_issues: Annotated[str, Form()] = "",
        caretaker_id: Annotated[str, Form()] = "",
        caretaker_name: Annotated[str, Form()] = "",
        harvest_images: Optional[UploadFile] = File(None),
        ):
    now = datetime.now(timezone.utc).isoformat()

    if not plant_type_ID.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected plant type is not linked to the plant catalog.",
        )
    try:
        try:
            farm = db.get_document(
                database_id=db_id,
                collection_id=db_collection_id2,
                document_id=farmID,
            )
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The selected farm no longer exists.",
            ) from error

        assigned_caretaker_id = str(farm.get("caretakerID") or "").strip()
        if not assigned_caretaker_id or assigned_caretaker_id.lower() == "unassigned":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assign a caretaker to this farm before creating a batch.",
            )
        if caretaker_id.strip() and caretaker_id.strip() != assigned_caretaker_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The selected caretaker is not assigned to this farm.",
            )
        caretaker_id = assigned_caretaker_id
        try:
            caretaker = db.get_document(
                database_id=db_id,
                collection_id=db_collection_id1,
                document_id=caretaker_id,
            )
            caretaker_name = str(caretaker.get("name") or caretaker_name).strip()
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The farm's assigned caretaker record no longer exists.",
            ) from error

        try:
            plant_type = db.get_document(
                database_id=db_id,
                collection_id=db_collection_id3,
                document_id=plant_type_ID,
            )
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The selected plant type no longer exists.",
            ) from error
        if plant_type.get("is_category") is True:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Select a plant type, not a plant category.",
            )

        farm_name = str(farm.get("name") or farm_name).strip()
        plant_name = str(plant_type.get("name") or plant_name).strip()

        file_id = ""
        view_url = ""
        download_url = ""
        if harvest_images is not None:
            file_bytes = await harvest_images.read()
            uploaded_file = st.create_file(
                bucket_id=bucket_id,
                file_id=ID.unique(),
                file=InputFile.from_bytes(file_bytes, filename=harvest_images.filename)
            )
            file_id = uploaded_file["$id"]
            view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
            download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"


        # Save URLs to Appwrite Database
        document_id = ID.unique()
        batches_info = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id5,
            document_id=document_id,
            data={
                "batch_id": document_id,
                "batch_no": batch_no,
                "farmID": farmID,
                "farm_name": farm_name,
                "plant_type_ID": plant_type_ID,
                "plant_name": plant_name,
                "plant_variety": plant_variety,
                "farm_manager_id": farm_manager_id,
                "farm_manager_name": farm_manager_name,
                "caretaker_id": caretaker_id,
                "caretaker_name": caretaker_name,   
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_seeds_nursed": total_seeds_nursed,   
                "total_harvested": 0,
                "total_transplanted": 0,
                "total_weight_kg": 0.0,
                "harvest_images": view_url,
                "production_status": ProductionStatus.PLANTED.value,
                "technical_issues": technical_issues.strip(),
                "inputs_supplied": "Batch created",
                "funds_requested": False,
                "financial_status": FinancialStatus.PENDING.value,
                "fund_request_id": "",
                "delivery_status": DeliveryStatus.PENDING.value,
                "delivery_details": "",
                "created_by": created_by,   
                "created_at": now,
                "updated_at": now
            }
        )
        return {
            "message": "Batches information created successfully",
             "batch_id": batches_info["$id"],
             "harvest_image_id": file_id,
             "harvest_image_url": view_url,
             "download_url": download_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create batch: {e}",
        ) from e

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
    
@collection5_router.get("/batches/{batch_id}")
def get_batch_info(batch_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id5,
            document_id= batch_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e))
    
@collection5_router.put("/batches/{batch_id}")
async def update_batch(batch_id:str,
    batch_no: Annotated[str, Form()],
    farmID: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    plant_type_ID: Annotated[str, Form()],
    plant_name: Annotated[str, Form()],
    plant_variety: Annotated[str, Form()],
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
    harvest_images: Annotated[UploadFile, File()],
    production_status: Annotated[ProductionStatus, Form()],
    technical_issues: Annotated[str, Form()],
    inputs_supplied: Annotated[str, Form()],
    funds_requested: Annotated[bool, Form()],
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
        "plant_variety": plant_variety,
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
                  "harvest_images": view_url,
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
            "batch_id": updated_doc["$id"],
            "updated_data": update_data,
            "harvest_image_id": file_id,
            "harvest_image_url": view_url,
            "download_url": download_url
        }

    except Exception as e:
        return {"error": str(e)}

@collection5_router.delete("/batches/{batch_id}")
def delete_batch(batch_no:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id5, 
            document_id=batch_no)
        return {"message": f"User with ID {batch_no} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
