from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id6
from db import db
from appwrite.id import ID
from appwrite.query import Query

collection6_router = APIRouter(tags=["Audits"])

class ActionType(str, Enum):
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"
    LOGIN = "Login"
    APPROVAL = "Approval"
    SUSPENSION = "Suspension"

class Status(str, Enum):
    ACTIVE = "Success"
    INACTIVE = "Failed"
    PENDING= "Pending"

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

@collection6_router.post("/audits/info")
def register_audit(
        action_type: Annotated[ActionType, Form()],
        collection_name: Annotated[str, Form()],
        performed_by_id: Annotated[str, Form()],
        performed_by_role: Annotated[Role, Form()],
        timestamp: Annotated[date, Form(...)],
        ip_address: Annotated[str, Form()],
        action_details: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        previous_data: Annotated[str, Form()],
        new_data: Annotated[str, Form()]
        ):    

    audits_info = {
        "audit_id": ID.unique(),
        "action_type": action_type,
        "collection_name": collection_name,
        "performed_by_id": performed_by_id,
        "performed_by_role": performed_by_role,
        "timestamp": timestamp.isoformat(),
        "ip_address": ip_address,
        "action_details": action_details,
        "status": status,
        "previous_data": previous_data,
        "new_data": new_data
    }
    print(audits_info)

    audit_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id6,
        document_id=ID.unique(),
        data= audits_info
    )

    return {
        "message": "User registered successfully",
        "farm_info_id": audit_create["$id"]
    }

@collection6_router.get("/audits")
def get_all_audit_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id6
        )

        # Extract the list of users
        audit_users = result["documents"]

        return {
            "count": len(audit_users),
            "users": audit_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection6_router.get("/audit/{audit_id}")
def get_audit_info(audit_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id6,
            document_id= audit_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection6_router.put("/audits/{audit_id}")
def update_audit(audit_id:str,
    action_type: Annotated[ActionType, Form()],
    collection_name: Annotated[str, Form()],
    performed_by_id: Annotated[str, Form()],
    performed_by_role: Annotated[Role, Form()],
    timestamp: Annotated[date, Form(...)],
    ip_address: Annotated[str, Form()],
    action_details: Annotated[str, Form()],
    status: Annotated[Status, Form()],
    previous_data: Annotated[str, Form()],
    new_data: Annotated[str, Form()]
    ):
    try:
        # Perform update
        updated_farm_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id6,
            document_id=audit_id,
            data={"action_type": action_type,
                  "collection_name": collection_name,
                  "performed_by_id": performed_by_id,
                  "performed_by_role": performed_by_role,
                  "timestamp": timestamp.isoformat(),
                  "ip_address": ip_address,
                  "action_details": action_details,
                  "status": status,
                  "previous_data": previous_data,
                  "new_data": new_data
            },
            permissions=[]
        )
        return {"message": "Audits info updated successfully", "user": updated_farm_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection6_router.delete("/audits/{audit_id}")
def delete_audit(audit_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id6, 
            document_id=audit_id)
        return {"message": f"User with ID {audit_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))