from fastapi import APIRouter, Form
from appwrite.services.account import Account
from appwrite.id import ID
from main import client
from pydantic import EmailStr
from typing import Annotated
from enum import Enum
# from appwrite.input_enum.authenticator_type import AuthenticatorType
import bcrypt
import smtplib
import os
from dotenv import load_dotenv

load_dotenv()


auth_router = APIRouter(tags=["Auth"])

account = Account(client)

class Role(str, Enum):
    SUPERADMIN = "superadmin"
    FARM_MANAGER = "farm_manager"
    FARM_OWNER = "farm_owner"
    CARETAKER = "caretaker"
    FULFILLMENT = "fulfillment_manager"
    PACKAGING_SUPERVISOR = "packaging_supervisor"
    QA = "quality_officer"
    SALES_MANAGER = "sales_manager"
    SALES_PERSON = "sales_person"
    ACCOUNTANT = "accountant"

EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_PORT= int(os.getenv("EMAIL_PORT"))
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_SECURITY = os.getenv("EMAIL_SECURITY")

# SIGNUP Endpoint
@auth_router.post("/account/signup")
def signup_user(
    name: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()]

):
    try:
        result = account.create(
            user_id=ID.unique(),
            email=email,
            password= password,
            name=name,
            confirm_password= confirm_password
        )
        return {"message": "User created successfully", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# magic url token
@auth_router.post("/account/tokens/magic-url")
def create_magic_url_token(user_id:Annotated[str, Form(...)],
                           email: Annotated[EmailStr, Form(...)]):
    try:
        result = account.create_magic_url_token(
            user_id = user_id,
            email = email,
            url = 'https://oyster-app-moqn5.ondigitalocean.app/', # optional
            phrase = False # optional
        )
        return {"message": f"Magic link sent to {email}", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# create session
@auth_router.post("/account/sessions/token")
def create_session(
    user_id:str,
    secret:str):
    try:
        result = account.create_session(
        user_id = user_id,
        secret = secret
    )
        return {"message": "User's session added successfully", "secret_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}


# SIGNIP WITH BCRYPT
@auth_router.post("/users/bcrypt")
def create_user_with_bcrypt(
    password: Annotated[str, Form()]
    ):
    try:
        # Hash the password using bcrypt
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        result = account.create_mfa_authenticator(
            type="totp"
        )
     
        return {"message": f"User created successfully {result}"} #"user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# email token
@auth_router.post("/account/tokens/email")
def create_email_token(
    user_id: str,
    email: Annotated[EmailStr , Form(...)]):
    try:
        result = account.create_email_token(
            user_id= user_id,
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

    
# create phone token
@auth_router.post("/account/tokens/phone")
def create_phone_token(
    user_id:str,
    phone:str):
    result = account.create_phone_token(
        user_id= user_id,
        phone= phone
    )
    return result

# email verification
@auth_router.post("/auth/verify")
def send_verification_email():
    try:
        verification = account.create_verification(url="https://oyster-app-moqn5.ondigitalocean.app/")
        return {"message": "Verification email sent", "verification_id": verification["$id"]}
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

# get session
@auth_router.get("/account/sessions/{sessionId}")
def get_session(session_id:str):
    result = account.get_session(
    session_id = session_id
)

# list sessions
@auth_router.get("/account/sessions")
def list_session():
    result = account.list_sessions()
    return result

# list logs 
@auth_router.get("/account/logs")
def list_logs():
    result = account.list_logs(
        queries=[]
    )
    return{"message": f"Logs list are; {result}"}

# update magic URL session
@auth_router.put("/account/sessions/magic-url")
def update_magic_URL_session(user_id:Annotated[str, Form(...)],
                           email: Annotated[EmailStr, Form(...)]):
    try:
        result = account.create_magic_url_token(
            user_id = user_id,
            email = email
            )
        return result
    except Exception as e:
        return {"error": str(e)}

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
    password: Annotated[str, Form(...)],
    old_password:Annotated[str, Form(...)]
):
    try:
        result = account.update_password(password = password,
                                         old_password= old_password)
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
def delete_account(identityId:str):
    try:
        result = account.delete_identity(
            identity_id=identityId
        )
        return {"message": f"User id{identityId} has been deleted successfully!"}
    except Exception as e:
        return {"error": str(e)}

# delete session
@auth_router.delete("/account/sessions")
def  delete_session():
    result = account.delete_sessions()