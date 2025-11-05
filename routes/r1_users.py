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
from main import client
from bcrypt import hashpw, gensalt, checkpw


collection1_router = APIRouter(tags=["Users"])


class Role(str, Enum):
    SUPERADMIN = "superadmin"
    FARM_MANAGER = "farm_manager"
    FARM_OWNER = "farm_owner"
    CARETAKER = "caretaker"
    TECHNICIANS = "technicians"
    FULFILLMENT = "fulfillment_manager"
    PACKAGING = "packaging_supervisor"
    QA = "quality_officer"
    SALES_MANAGER = "sales_manager"
    SALES_PERSON = "sales_person"
    ACCOUNTANT = "accountant"

class UserUpdateModel(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    address: str | None = None
    farmID: str | None = None


@collection1_router.post("/users/signup")
def register_user(
        name: Annotated[str, Form()],
        email: Annotated[EmailStr, Form()],
        password: Annotated[str, Form()],
        address: Annotated[str, Form()],
        role: Annotated[Role, Form()],
        phone: Annotated[str, Form()]
        ):

    existing = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id1,
        queries=[Query.equal("email", email)]
    )
    if existing["total"] > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"User with email {email} already exists!")

    user_created = {
        "name": name,
        "email": email,
        "password": password,
        "role": role,
        "address": address,
        "phone": phone
    }

    registered_user = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id1,
        document_id=ID.unique(),
        data= user_created
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
    phone: Annotated[Role, Form()]):
    try:
        # Perform update
        updated_user = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id1,
            document_id=user_id,
            data={"name": name,
                  "email": email,
                  "password": password,
                  "role": role,
                  "address": address,
                  "phone": phone
            },
            permissions=[]
        )
        return {"message": "User updated successfully", "user": updated_user}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection1_router.delete("/users/{user_id}")
def delete_user(user_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id1, 
            document_id=user_id)
        return {"message": f"User with ID {user_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
