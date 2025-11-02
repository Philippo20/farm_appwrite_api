from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id8
from db import db
from appwrite.id import ID
from appwrite.query import Query

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
def register_wallet(
        user_id: Annotated[str, Form()],
        user_name: Annotated[str, Form()],
        role: Annotated[Role, Form()],
        balance: Annotated[float, Form()],
        currency: Annotated[str, Form()],
        total_credits: Annotated[float, Form()],
        total_debits: Annotated[float, Form()],
        transaction_image: Annotated[str, Form()],
        transaction_id: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        created_at: Annotated[date, Form(...)],
        updated_at: Annotated[datetime, Form(...)],
        created_by: Annotated[str, Form()]
        ):
    sales_info = {
        "wallet_id": ID.unique(),
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
    print(sales_info)

    fulfillment_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id8,
        document_id=ID.unique(),
        data= sales_info
    )

    return {
        "message": "User registered successfully",
        "fulfillment_id": fulfillment_create["$id"]
    }

@collection10_router.get("/wallet")
def get_all_wallet_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id8
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
            collection_id= db_collection_id8,
            document_id= wallet_id
        )
        return wallet
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection10_router.put("/wallet/{wallet_id}")
def update_wallet(wallet_id:str,
    user_name: Annotated[str, Form()],
    role: Annotated[Role, Form()],
    balance: Annotated[float, Form()],
    currency: Annotated[str, Form()],
    total_credits: Annotated[float, Form()],
    total_debits: Annotated[float, Form()],
    transaction_image: Annotated[str, Form()],
    transaction_id: Annotated[str, Form()],
    status: Annotated[Status, Form()],
    created_at: Annotated[date, Form(...)],
    updated_at: Annotated[datetime, Form(...)],
    created_by: Annotated[str, Form()]
    ):
    try:
        # Perform update
        updated_wallet_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id8,
            document_id=wallet_id,
            data={"user_id": wallet_id,
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
            },
            permissions=[]
        )
        return {"message": "Wallet info updated successfully", "user": updated_wallet_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection10_router.delete("/wallet/{wallet_id}")
def delete_wallet(wallet_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id8, 
            document_id=wallet_id)
        return {"message": f"User with ID {wallet_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))