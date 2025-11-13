from fastapi import APIRouter, Form, File, UploadFile, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id10,bucket_id, project_id, appwrite_endpoint
from db import db
from appwrite.id import ID
from appwrite.query import Query
from appwrite.input_file import InputFile
from storage import st

collection10_router = APIRouter(tags=["Wallet"])

class Role(str, Enum):
    ROLE_SUPERADMIN = "superadmin"
    ROLE_FARM_MANAGER = "farm_manager"
    ROLE_FARM_OWNER = "farm_owner"
    ROLE_CARETAKER = "caretaker"
    ROLE_TECHNICIANS = "technicians"
    ROLE_FULFILLMENT = "fulfillment_manager"
    ROLE_PACKAGING = "packaging_supervisor"
    ROLE_QA = "quality_officer"
    ROLE_SALES_MANAGER = "sales_manager"
    ROLE_SALES_PERSON = "sales_person"
    ROLE_ACCOUNTANT = "accountant"

class Status(str, Enum):
    ACTIVE = "Active"
    FROZEN = "Frozen"
    CLOSED = "Closed"

@collection10_router.post("/wallet/info")
async def register_wallet(
        user_id: Annotated[str, Form()],
        user_name: Annotated[str, Form()],
        role: Annotated[Role, Form()],
        balance: Annotated[float, Form()],
        currency: Annotated[str, Form()],
        total_credits: Annotated[float, Form()],
        total_debits: Annotated[float, Form()],
        transaction_image: Annotated[UploadFile, File()],
        transaction_id: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        created_at: Annotated[date, Form(...)],
        updated_at: Annotated[datetime, Form(...)],
        created_by: Annotated[str, Form()]
        ):
    file_bytes = await transaction_image.read()
    
    try:
        # Upload file to Appwrite Storage
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=transaction_image.filename)
        )
        file_id = uploaded_file["$id"]

        # Generate file URLs
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"

        # Save URLs to Appwrite Database
        saved_doc = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id10,
            document_id=ID.unique(),
            data={
                "user_id": user_id,
                "user_name": user_name,
                "role": role,
                "balance": balance,
                "currency": currency,
                "total_credits": total_credits,
                "total_debits": total_debits,
                "transaction_image": transaction_image.filename,
                "transaction_id": transaction_id,
                "status": status,
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat(),
                "created_by": created_by
                }
        )

        return {
            "message": "File created successfully",
            "file_id": file_id,
            "view_url": view_url,
            "download_url": download_url,
            "wallet_id": saved_doc["$id"]
        }

    except Exception as e:
        return {"error": str(e)}
    

@collection10_router.get("/wallet")
def get_all_wallet_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id10
        )

        # Extract the list of users
        wallet_users = result["documents"]

        return {
            "count": len(wallet_users),
            "users": wallet_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection10_router.get("/wallet/{wallet_id}")
def get_wallet_info(wallet_id:str):
    try:
        wallet= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id10,
            document_id= wallet_id
        )
        return wallet
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection10_router.put("/wallet/{wallet_id}")
async def update_wallet(wallet_id:str,
        user_id: Annotated[str, Form()],                 
        user_name: Annotated[str, Form()],
        role: Annotated[Role, Form()],
        balance: Annotated[float, Form()],
        currency: Annotated[str, Form()],
        total_credits: Annotated[float, Form()],
        total_debits: Annotated[float, Form()],
        transaction_image: Annotated[UploadFile, File()],
        transaction_id: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        created_at: Annotated[date, Form(...)],
        updated_at: Annotated[datetime, Form(...)],
        created_by: Annotated[str, Form()]
    ):
    update_data = {}

    # If a new image is uploaded, replace the old one
    if transaction_image:
        file_bytes = await transaction_image.read()
        uploaded_file = st.create_file(
            bucket_id=bucket_id,
            file_id=ID.unique(),
            file=InputFile.from_bytes(file_bytes, filename=transaction_image.filename)
        )

        file_id = uploaded_file["$id"]
        view_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/view?project={project_id}"
        download_url = f"{appwrite_endpoint}/storage/buckets/{bucket_id}/files/{file_id}/download?project={project_id}"

    # Only include fields that were actually provided
    form_fields = {
        "user_id": user_id,
        "user_name": user_name,
        "role": role,
        "balance": balance,
        "currency": currency,
        "total_credits": total_credits,
        "total_debits": total_debits,
        "transaction_image": transaction_image,
        "transaction_id": transaction_id,
        "status": status,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
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
            collection_id=db_collection_id10,
            document_id=wallet_id,
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
    
@collection10_router.delete("/wallet/{wallet_id}")
def delete_wallet(wallet_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id10, 
            document_id=wallet_id)
        return {"message": f"User with ID {wallet_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    