from fastapi import APIRouter, Form, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Annotated
from enum import Enum
from main import db_id, db_collection_id1
from db import db
from appwrite.query import Query
from appwrite.id import ID
from appwrite.client import Client
from appwrite.services.account import Account
from appwrite.services.users import Users
from main import client
from bcrypt import hashpw, gensalt, checkpw
from audit_utils import write_audit


collection1_router = APIRouter(tags=["Users"])
account = Account(client)
auth_users = Users(client)


class Role(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    FARM_MANAGER = "farm_manager"
    FARM_OWNER = "farm_owner"
    CARETAKER = "caretaker"
    TECHNICIANS = "technician"
    FULFILLMENT = "fulfillment_manager"
    PACKAGING = "packaging_supervisor"
    QA = "quality_officer"
    SALES_MANAGER = "sales_manager"
    SALES_PERSON = "sales_person"
    ACCOUNTANT = "accountant"
    DRIVER = "driver"

class UserStatus(str, Enum):
    ACTIVE = "Active"
    PENDING = "Pending"
    SUSPENDED = "Suspended"

class UserUpdateModel(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    status: str | None = None
    address: str | None = None
    phone: str | None = None
    department: str | None = None
    farmID: str | None = None


@collection1_router.post("/users/signup")
def register_user(
        name: Annotated[str, Form()],
        email: Annotated[EmailStr, Form()],
        password: Annotated[str, Form()],
        address: Annotated[str, Form()],
        role: Annotated[Role, Form()],
        phone: Annotated[str, Form()],
        department: Annotated[str, Form()],
        user_status: Annotated[UserStatus, Form(alias="status")] = UserStatus.ACTIVE
        ):

    existing = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id1,
        queries=[Query.equal("email", email)]
    )
    if existing["total"] > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"User with email {email} already exists!")

    user_id = ID.unique()
    try:
        account.create(
            user_id=user_id,
            email=email,
            password=password,
            name=name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth user creation failed: {e}")

    user_created = {
        "name": name,
        "email": email,
        "password": password,
        "role": role,
        "status": user_status,
        "address": address,
        "phone": phone,
        "department": department
    }

    registered_user = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id1,
        document_id=user_id,
        data= user_created
    )
    write_audit(
        action_type="Create",
        collection_name="Users",
        performed_by_id=user_id,
        performed_by_role=role.value,
        action_details=f"Created user {email}",
        new_data={**user_created, "password": "***"}
    )

    return {
        "message": "User registered successfully",
        "user_id": registered_user["$id"]
    }

@collection1_router.get("/users")
def get_all_users():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id1
        )

        # Extract the list of users
        users = result["documents"]

        return {
            "count": len(users),
            "users": users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection1_router.get("/users/{user_id}")
def get_user(user_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id1,
            document_id= user_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection1_router.put("/users/{user_id}")
def update_user(
    user_id:str, 
    name: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()],
    address: Annotated[str, Form()],
    role: Annotated[Role, Form()],
    phone: Annotated[str, Form()],
    department: Annotated[str, Form()],
    user_status: Annotated[UserStatus, Form(alias="status")] = UserStatus.ACTIVE):
    try:
        previous_user = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id1,
            document_id=user_id
        )
        # Perform update
        update_data = {"name": name,
                  "email": email,
                  "password": password,
                  "role": role,
                  "status": user_status,
                  "address": address,
                  "phone": phone,
                  "department": department
            }
        updated_user = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id1,
            document_id=user_id,
            data=update_data,
            permissions=[]
        )
        try:
            auth_users.update_name(user_id=user_id, name=name)
            auth_users.update_email(user_id=user_id, email=email)
            if password:
                auth_users.update_password(user_id=user_id, password=password)
        except Exception:
            pass
        write_audit(
            action_type="Update",
            collection_name="Users",
            performed_by_id=user_id,
            performed_by_role=role.value,
            action_details=f"Updated user {email}",
            previous_data=previous_user,
            new_data={**update_data, "password": "***"}
        )
        return {"message": "User updated successfully", "user": updated_user}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection1_router.delete("/users/{user_id}")
def delete_user(user_id:str):
    try:
        previous_user = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id1,
            document_id=user_id
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id1, 
            document_id=user_id)
        try:
            auth_users.delete(user_id=user_id)
        except Exception:
            pass
        write_audit(
            action_type="Delete",
            collection_name="Users",
            performed_by_id=user_id,
            performed_by_role="superadmin",
            action_details=f"Deleted user {previous_user.get('email', user_id)}",
            previous_data=previous_user
        )
        return {"message": f"User with ID {user_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
