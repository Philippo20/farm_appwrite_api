from fastapi import APIRouter, Form, Header, HTTPException
from appwrite.services.account import Account
from appwrite.services.users import Users
from appwrite.client import Client
from appwrite.id import ID
from main import client
from pydantic import EmailStr
from typing import Annotated, Optional
from enum import Enum
# from appwrite.input_enum.authenticator_type import AuthenticatorType
import bcrypt
import smtplib
import os
from dotenv import load_dotenv

load_dotenv()


user_auth_router = APIRouter(tags=["Auth"])

# Admin account for server operations (signup, create session)
account = Account(client)

# Helper function to create user-specific client with JWT
def get_user_client(jwt_token: str) -> Client:
    """Create Appwrite client with user JWT token"""
    user_client = Client()
    user_client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
    user_client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
    user_client.set_jwt(jwt_token)
    return user_client

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
@user_auth_router.post("/account/signup")
def signup_user(
    name: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()]

):
    try:
        result = account.create(
            user_id=ID.unique(),
            email=email,
            password= password,
            name=name
        )
        return {"message": "User created successfully", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# magic url token
@user_auth_router.post("/account/tokens/magic-url")
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
@user_auth_router.post("/account/sessions/token")
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
@user_auth_router.post("/users/bcrypt")
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
@user_auth_router.post("/account/tokens/email")
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
@user_auth_router.post("/account/jwts")
def create_jwt(authorization: Annotated[Optional[str], Header()] = None):
    """
    Create JWT token from existing session
    Can use either session cookie or Authorization header
    """
    try:
        if authorization:
            # If JWT already exists, create a new one using the existing one
            jwt_token = authorization.replace("Bearer ", "")
            user_client = get_user_client(jwt_token)
            user_account = Account(user_client)
            result = user_account.create_jwt()
        else:
            # Use session cookie
            result = account.create_jwt()
        
        return {
            "jwt": result.get("jwt"),
            "message": "JWT created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"JWT creation failed: {str(e)}")

    
# create phone token
@user_auth_router.post("/account/tokens/phone")
def create_phone_token(
    user_id:str,
    phone:str):
    result = account.create_phone_token(
        user_id= user_id,
        phone= phone
    )
    return result

# email verification
@user_auth_router.post("/auth/verify")
def send_verification_email():
    try:
        verification = account.create_verification(url="https://oyster-app-moqn5.ondigitalocean.app/")
        return {"message": "Verification email sent", "verification_id": verification["$id"]}
    except Exception as e:
        return {"error": str(e)}

# login 
@user_auth_router.post("/account/login")
def login_user(
    email: Annotated[EmailStr, Form(...)],
    password: Annotated[str, Form(...)]
):
    """
    Login user and return JWT token
    Returns session details with JWT for authenticated requests
    """
    try:
        # Create email/password session
        session = account.create_email_password_session(
            email=email,
            password=password
        )
        
        # Create JWT token from the session
        jwt_result = account.create_jwt()
        
        return {
            "message": "Login successful",
            "session_id": session["$id"],
            "jwt": jwt_result.get("jwt"),  # Return JWT token
            # "secret": jwt_result.get("secret")  # Secret for session management
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Login failed: {str(e)}")

# get account user 
@user_auth_router.get("/account")
def get_account_user(authorization: Annotated[str, Header()]):
    """
    Get current user account details
    Requires: Authorization header with Bearer token (JWT from login)
    """
    try:
        # Extract JWT from "Bearer <token>"
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        jwt_token = authorization.replace("Bearer ", "")
        
        # Create user-specific client with JWT
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        # Get account with user permissions
        result = user_account.get()
        return result
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# get account preferences
@user_auth_router.get("/account/prefs")
def get_account_prefs(authorization: Annotated[str, Header()]):
    """Get user preferences - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.get_prefs()
        return result
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Failed to get preferences: {str(e)}")

# get session
@user_auth_router.get("/account/sessions/{sessionId}")
def get_session(session_id: str, authorization: Annotated[str, Header()]):
    """Get specific session - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.get_session(session_id=session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Failed to get session: {str(e)}")

# list sessions
@user_auth_router.get("/account/sessions")
def list_session(authorization: Annotated[str, Header()]):
    """List all user sessions - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.list_sessions()
        return result
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Failed to list sessions: {str(e)}")

# list logs 
@user_auth_router.get("/account/logs")
def list_logs(authorization: Annotated[str, Header()]):
    """List user activity logs - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.list_logs(queries=[])
        return {"message": f"Logs list retrieved", "logs": result}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Failed to list logs: {str(e)}")

# update magic URL session
@user_auth_router.put("/account/sessions/magic-url")
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
@user_auth_router.patch("/account/email")
def update_email(
    email: Annotated[EmailStr, Form(...)],
    password: Annotated[str, Form(...)],
    authorization: Annotated[str, Header()]
):
    """Update user email - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.update_email(email=email, password=password)
        return {"message": "Email updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update email: {str(e)}")
    
# update name 
@user_auth_router.patch("/account/name")
def update_name(
    name: Annotated[str, Form(...)],
    authorization: Annotated[str, Header()]
):
    """Update user name - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.update_name(name=name)
        return {"message": "Name updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update name: {str(e)}")


# update password 
@user_auth_router.patch("/account/password")
def update_password(
    password: Annotated[str, Form(...)],
    old_password: Annotated[str, Form(...)],
    authorization: Annotated[str, Header()]
):
    """Update user password - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.update_password(password=password, old_password=old_password)
        return {"message": "Password updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update password: {str(e)}")


# update phone 
@user_auth_router.patch("/account/phone")
def update_phone(
    phone: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    authorization: Annotated[str, Header()]
):
    """Update user phone - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.update_phone(phone=phone, password=password)
        return {"message": "Phone number updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update phone: {str(e)}")

@user_auth_router.patch("/account/prefs")
def update_prefs(
    prefs: dict,
    authorization: Annotated[str, Header()]
):
    """Update user preferences - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.update_prefs(prefs=prefs)
        return {"message": "Preferences updated successfully!", "prefs": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update preferences: {str(e)}")

# delete account user 
@user_auth_router.delete("/account/identities/{identityId}")
def delete_account(
    identityId: str,
    authorization: Annotated[str, Header()]
):
    """Delete user identity - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.delete_identity(identity_id=identityId)
        return {"message": f"Identity {identityId} has been deleted successfully!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete identity: {str(e)}")

# delete session
@user_auth_router.delete("/account/sessions")
def delete_session(authorization: Annotated[str, Header()]):
    """Delete all user sessions (logout) - requires JWT"""
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.delete_sessions()
        return {"message": "All sessions deleted successfully (logged out)"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete sessions: {str(e)}")