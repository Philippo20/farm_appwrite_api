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
    driver_license_number: str | None = None
    vehicle: str | None = None
    vehicle_type: str | None = None
    vehicle_capacity_kg: float | None = None


def _validate_driver_manager(role: Role, actor_role: str):
    if role != Role.DRIVER:
        return
    normalized_actor = actor_role.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized_actor not in {Role.ADMIN.value, Role.SUPERADMIN.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an Admin or Super Admin can create or update Driver accounts.",
        )


def _validate_driver_profile(
    role: Role,
    driver_license_number: str,
    vehicle: str,
    vehicle_type: str,
    vehicle_capacity_kg: float,
):
    if role != Role.DRIVER:
        return
    if not all(
        value.strip() for value in (driver_license_number, vehicle, vehicle_type)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Driver license number, vehicle registration, and vehicle type "
                "are required for Driver accounts."
            ),
        )
    if vehicle_capacity_kg < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vehicle capacity cannot be negative.",
        )


@collection1_router.post("/users/signup")
def register_user(
        name: Annotated[str, Form()],
        email: Annotated[EmailStr, Form()],
        password: Annotated[str, Form()],
        address: Annotated[str, Form()],
        role: Annotated[Role, Form()],
        phone: Annotated[str, Form()],
        department: Annotated[str, Form()],
        user_status: Annotated[UserStatus, Form(alias="status")] = UserStatus.ACTIVE,
        actor_id: Annotated[str, Form()] = "",
        actor_role: Annotated[str, Form()] = "",
        driver_license_number: Annotated[str, Form()] = "",
        vehicle: Annotated[str, Form()] = "",
        vehicle_type: Annotated[str, Form()] = "",
        vehicle_capacity_kg: Annotated[float, Form()] = 0,
        ):

    _validate_driver_manager(role, actor_role)
    _validate_driver_profile(
        role,
        driver_license_number,
        vehicle,
        vehicle_type,
        vehicle_capacity_kg,
    )

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
        "department": department,
        "driver_license_number": driver_license_number.strip() if role == Role.DRIVER else "",
        "vehicle": vehicle.strip() if role == Role.DRIVER else "",
        "vehicle_type": vehicle_type.strip() if role == Role.DRIVER else "",
        "vehicle_capacity_kg": max(vehicle_capacity_kg, 0) if role == Role.DRIVER else 0,
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
        performed_by_id=actor_id.strip() or user_id,
        performed_by_role=actor_role.strip() or role.value,
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


@collection1_router.patch("/users/{user_id}/profile")
def update_user_profile(
    user_id: str,
    name: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    address: Annotated[str, Form()] = "",
):
    try:
        previous_user = db.get_document(
            database_id=db_id, collection_id=db_collection_id1, document_id=user_id
        )
        update_data = {"name": name.strip(), "email": str(email), "address": address.strip()}
        updated_user = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id1,
            document_id=user_id,
            data=update_data,
            permissions=[],
        )
        try:
            auth_users.update_name(user_id=user_id, name=name.strip())
            auth_users.update_email(user_id=user_id, email=str(email))
        except Exception:
            pass
        write_audit(
            action_type="Update",
            collection_name="Users",
            performed_by_id=user_id,
            performed_by_role=previous_user.get("role", "caretaker"),
            action_details="Updated caretaker profile",
            previous_data=previous_user,
            new_data=update_data,
        )
        return {"message": "Profile updated successfully", "user": updated_user}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection1_router.patch("/users/{user_id}/password")
def update_user_password(user_id: str, password: Annotated[str, Form()]):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    try:
        previous_user = db.get_document(
            database_id=db_id, collection_id=db_collection_id1, document_id=user_id
        )
        auth_users.update_password(user_id=user_id, password=password)
        updated_user = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id1,
            document_id=user_id,
            data={"password": password},
            permissions=[],
        )
        write_audit(
            action_type="Update",
            collection_name="Users",
            performed_by_id=user_id,
            performed_by_role=previous_user.get("role", "caretaker"),
            action_details="Updated account password",
            previous_data={"password": "***"},
            new_data={"password": "***"},
        )
        return {"message": "Password updated successfully", "user": updated_user}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    
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
    user_status: Annotated[UserStatus, Form(alias="status")] = UserStatus.ACTIVE,
    actor_id: Annotated[str, Form()] = "",
    actor_role: Annotated[str, Form()] = "",
    driver_license_number: Annotated[str, Form()] = "",
    vehicle: Annotated[str, Form()] = "",
    vehicle_type: Annotated[str, Form()] = "",
    vehicle_capacity_kg: Annotated[float, Form()] = 0,
    ):
    try:
        previous_user = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id1,
            document_id=user_id
        )
        if role == Role.DRIVER or previous_user.get("role") == Role.DRIVER.value:
            _validate_driver_manager(Role.DRIVER, actor_role)
        _validate_driver_profile(
            role,
            driver_license_number,
            vehicle,
            vehicle_type,
            vehicle_capacity_kg,
        )
        # Perform update
        update_data = {"name": name,
                  "email": email,
                  "password": password,
                  "role": role,
                  "status": user_status,
                  "address": address,
                  "phone": phone,
                  "department": department,
                  "driver_license_number": driver_license_number.strip() if role == Role.DRIVER else "",
                  "vehicle": vehicle.strip() if role == Role.DRIVER else "",
                  "vehicle_type": vehicle_type.strip() if role == Role.DRIVER else "",
                  "vehicle_capacity_kg": max(vehicle_capacity_kg, 0) if role == Role.DRIVER else 0,
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
            performed_by_id=actor_id.strip() or user_id,
            performed_by_role=actor_role.strip() or role.value,
            action_details=f"Updated user {email}",
            previous_data=previous_user,
            new_data={**update_data, "password": "***"}
        )
        return {"message": "User updated successfully", "user": updated_user}

    except HTTPException:
        raise
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
