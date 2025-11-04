from fastapi import APIRouter, Form
from appwrite.services.account import Account
from appwrite.id import ID
from main import client
from pydantic import EmailStr
from typing import Annotated
from enum import Enum
from bcrypt import hashpw, gensalt, checkpw


auth_router = APIRouter(tags=["Auth"])

account = Account(client)

class Role(str, Enum):
    ROLE_SUPERADMIN = "superadmin"
    ROLE_FARM_MANAGER = "farm_manager"
    ROLE_FARM_OWNER = "farm_owner"
    ROLE_CARETAKER = "caretaker"
    ROLE_FULFILLMENT = "fulfillment_manager"
    ROLE_PACKAGING = "packaging_supervisor"
    ROLE_QA = "quality_officer"
    ROLE_SALES_MANAGER = "sales_manager"
    ROLE_SALES_PERSON = "sales_person"
    ROLE_ACCOUNTANT = "accountant"

# SIGNUP Endpoint
@auth_router.post("/account/signup")
def signup_user(
    name: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()],
    address: Annotated[str, Form()],
    role: Annotated[Role, Form()],
    phone: Annotated[str, Form()],
    department: Annotated[str, Form()]
):
    try:
        result = account.create(
            user_id=ID.unique(),
            email=email,
            password= password,
            name=name,
            address=address,
            role= role,
            phone= phone,
            department= department
        )
        return {"message": "User created successfully", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# SIGNIP WITH BCRYPT
@auth_router.post("/users/bcrypt")
def create_user_with_bcrypt(
    name: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()],
    address: Annotated[str, Form()],
    role: Annotated[Role, Form()],
    phone: Annotated[str, Form()],
    department: Annotated[str, Form()]
    ):
    try:
        result = account.create_mfa_authenticator(
            user_id=ID.unique(),
            email= email,
            password= password,
            name= name,
            address= address,
            role= role,
            phone= phone,
            department= department
        )
     
        return {"message": "User created successfully", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# email token
@auth_router.post("/account/tokens/email")
def create_email_token(email: Annotated[EmailStr , Form(...)]):
    try:
        result = account.create_email_token(
            user_id=ID.unique(),
            email= email,
            phrase= False
        )
        return {"message": "User's email token created successfully", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# jwt
@auth_router.post("/account/jwts")
def create_jwt():
    try:
        result = account.create_jwt()
        return {"message": "User's token created successfully", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# magic url token
@auth_router.post("/account/tokens/magic-url")
def create_magic_url_token():
    try:
        result = account.create_magic_url_token(
            user_id = '<USER_ID>',
            email = 'email@example.com',
            url = 'https://example.com', # optional
            phrase = False # optional
        )
        return {"message": "Magic link sent to email", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# login 
@auth_router.post("/account/login")
def login_user(
    email: Annotated[EmailStr, Form(...)],
    password: Annotated[str, Form(...)]
):
    try:
        session = account.create_email_password_session(
            email=email,
            password=password
        )
        return {"message": "Login successful", "session_id": session["$id"]}
    except Exception as e:
        return {"error": str(e)}
    
# email verification
@auth_router.post("/auth/verify")
def send_verification_email():
    try:
        verification = account.create_verification(url="https://your-frontend.com/verify")
        return {"message": "Verification email sent", "verification_id": verification["$id"]}
    except Exception as e:
        return {"error": str(e)}

# get account user 
@auth_router.get("/account")
def get_account_user():
    result = account.get()
    return result

# get account preferences
@auth_router.get("/account/prefs")
def get_account_prefs():
    result = account.get_prefs()
    return result

# update email 
@auth_router.put("/account/email")
def update_email(
    email: Annotated[EmailStr , Form(...)],
    password: Annotated[str, Form()]
):
    try:
        result = account.update_email(
            email = email,
            password=password)
        return {"message": "email updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}
    
# update name 
@auth_router.put("/account/name")
def update_name(
    name: Annotated[str, Form(...)]
):
    try:
        result = account.update_name(name= name)
        return {"message": "name updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}


# update password 
@auth_router.put("/account/password")
def update_password(
    password: Annotated[str, Form(...)]
):
    try:
        result = account.update_password(password = password)
        return {"message": "name updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}


# update phone 
@auth_router.put("/account/phone")
def update_phone (phone: Annotated[str, Form(...)]):
    try:
        result = account.update_phone(phone= phone)
        return {"message": "phone number updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

@auth_router.put("/account/prefs")
def update_prefs():
    try:
        result = account.update_prefs(
            prefs={
                "language": "en",
                "timezone": "UTC",
                "darkTheme": True
            }
        )
        return {"message": "User id{user_id} has been deleted successfully!"}
    except Exception as e:
        return {"error": str(e)}

# delete account user 
@auth_router.delete("/account/identities/{identityId}")
def delete_account(user_id:str):
    try:
        result = account.delete_identity(
            identity_id=user_id
        )
        return {"message": "User id{user_id} has been deleted successfully!"}
    except Exception as e:
        return {"error": str(e)}
