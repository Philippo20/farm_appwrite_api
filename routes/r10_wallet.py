from fastapi import APIRouter, Form, File, UploadFile, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, timezone
from main import db_id, db_collection_id10,bucket_id, project_id, appwrite_endpoint
from db import db
from appwrite.id import ID
from appwrite.query import Query
from appwrite.input_file import InputFile
from storage import st
from audit_utils import write_audit

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

class WithdrawalStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    PAID = "Paid"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _withdrawal_code() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"WD-{stamp}"

def _wallet_document(
        *,
        user_id: str,
        user_name: str,
        role: str,
        balance: float,
        currency: str,
        total_credits: float,
        total_debits: float,
        transaction_image: str,
        transaction_id: str,
        status_value: str,
        created_by: str,
        transaction_type: str = "Balance",
        withdrawal_status: str = "",
        amount: float = 0,
        bank_account: str = "",
        note: str = "",
        farm_id: str = "",
        farm_name: str = "",
        requested_at: str = "",
        processed_at: str = "",
        decision_notes: str = "",
        account_name: str = "",
        account_number: str = "",
        bank_name: str = "",
        payout_method: str = "",
):
    data = {
        "user_id": user_id,
        "user_name": user_name,
        "role": role,
        "balance": balance,
        "currency": currency,
        "total_credits": total_credits,
        "total_debits": total_debits,
        "transaction_image": transaction_image,
        "transaction_id": transaction_id,
        "status": status_value,
        "created_by": created_by,
        "transaction_type": transaction_type,
    }
    optional_fields = {
        "withdrawal_status": withdrawal_status,
        "amount": amount,
        "bank_account": bank_account,
        "note": note,
        "farm_id": farm_id,
        "farm_name": farm_name,
        "requested_at": requested_at,
        "processed_at": processed_at,
        "decision_notes": decision_notes,
        "account_name": account_name,
        "account_number": account_number,
        "bank_name": bank_name,
        "payout_method": payout_method,
    }
    for key, value in optional_fields.items():
        if value not in ["", None]:
            data[key] = value
    return data

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

@collection10_router.post("/wallet/withdrawals")
def create_wallet_withdrawal(
        user_id: Annotated[str, Form()],
        user_name: Annotated[str, Form()],
        farm_id: Annotated[str, Form()],
        farm_name: Annotated[str, Form()],
        amount: Annotated[float, Form()],
        bank_account: Annotated[str, Form()],
        note: Annotated[str, Form()] = "",
        currency: Annotated[str, Form()] = "GHS",
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Withdrawal amount must be greater than zero")
    if not bank_account.strip():
        raise HTTPException(status_code=400, detail="Bank account is required")

    transaction_id = _withdrawal_code()
    data = _wallet_document(
        user_id=user_id,
        user_name=user_name,
        role=Role.ROLE_FARM_OWNER.value,
        balance=0,
        currency=currency,
        total_credits=0,
        total_debits=amount,
        transaction_image="",
        transaction_id=transaction_id,
        status_value=Status.ACTIVE.value,
        created_by=user_name or user_id,
        transaction_type="Withdrawal",
        withdrawal_status=WithdrawalStatus.PENDING.value,
        amount=amount,
        bank_account=bank_account,
        note=note,
        farm_id=farm_id,
        farm_name=farm_name,
        requested_at=_now(),
    )

    try:
        created = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id10,
            document_id=ID.unique(),
            data=data,
        )
        write_audit(
            action_type="Create",
            collection_name="Wallet",
            performed_by_id=user_name or user_id,
            performed_by_role=Role.ROLE_FARM_OWNER.value,
            action_details=f"Created wallet withdrawal {transaction_id}",
            new_data=data,
        )
        return {
            "message": "Withdrawal request submitted successfully",
            "withdrawal": created,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@collection10_router.post("/wallet/bank-accounts")
def create_wallet_bank_account(
        user_id: Annotated[str, Form()],
        user_name: Annotated[str, Form()],
        bank_name: Annotated[str, Form()],
        account_name: Annotated[str, Form()],
        account_number: Annotated[str, Form()],
        payout_method: Annotated[str, Form()] = "Bank",
        currency: Annotated[str, Form()] = "GHS",
):
    clean_method = payout_method.strip() or "Bank"
    clean_bank = bank_name.strip()
    clean_account_name = account_name.strip()
    clean_account_number = account_number.strip()
    if clean_method not in ["Bank", "Mobile Money"]:
        raise HTTPException(status_code=400, detail="Payout method must be Bank or Mobile Money")
    if not clean_bank:
        raise HTTPException(
            status_code=400,
            detail="Bank name is required" if clean_method == "Bank" else "Mobile money network is required",
        )
    if not clean_account_name:
        raise HTTPException(
            status_code=400,
            detail="Account name is required" if clean_method == "Bank" else "Mobile money account name is required",
        )
    if not clean_account_number:
        raise HTTPException(
            status_code=400,
            detail="Account number is required" if clean_method == "Bank" else "Mobile money number is required",
        )

    masked_number = clean_account_number[-4:].rjust(min(len(clean_account_number), 4), "*")
    bank_account = f"{clean_method}: {clean_bank} - ****{masked_number[-4:]}"
    data = _wallet_document(
        user_id=user_id,
        user_name=user_name,
        role=Role.ROLE_FARM_OWNER.value,
        balance=0,
        currency=currency,
        total_credits=0,
        total_debits=0,
        transaction_image="",
        transaction_id=f"BA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        status_value=Status.ACTIVE.value,
        created_by=user_name or user_id,
        transaction_type="Payout Account",
        bank_account=bank_account,
        requested_at=_now(),
        account_name=clean_account_name,
        account_number=clean_account_number,
        bank_name=clean_bank,
        payout_method=clean_method,
    )

    try:
        created = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id10,
            document_id=ID.unique(),
            data=data,
        )
        write_audit(
            action_type="Create",
            collection_name="Wallet",
            performed_by_id=user_name or user_id,
            performed_by_role=Role.ROLE_FARM_OWNER.value,
            action_details=f"Added {clean_method.lower()} payout account for {clean_bank}",
            new_data={**data, "account_number": bank_account},
        )
        return {
            "message": "Payout account added successfully",
            "account": created,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

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
