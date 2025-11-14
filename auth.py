from fastapi import APIRouter, Form, Header, HTTPException
from appwrite.services.account import Account
from appwrite.services.users import Users
from appwrite.client import Client
from appwrite.id import ID
from main import client, db_id, db_collection_id1
from db import db
from appwrite.query import Query
from pydantic import EmailStr
from typing import Annotated, Optional
from enum import Enum
import bcrypt
import smtplib
import os
from dotenv import load_dotenv
import jwt
import datetime

load_dotenv()


auth_router = APIRouter(tags=["Auth"])

account = Account(client)

# Helper function to create user-specific client with JWT or session
def get_user_client(token: str) -> Client:
    """Create Appwrite client with user token (decodes JWT to get user_id)"""
    try:
        # Decode JWT to get user_id
        jwt_secret = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user_id")
        
        # Note: This returns an admin client - we'll use Users service to get user data
        return client, user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")

# Helper function to create user-specific client with session ID
def get_session_client(session_id: str) -> Client:
    """Create Appwrite client with session ID"""
    user_client = Client()
    user_client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
    user_client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
    user_client.set_session(session_id)
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

# Test endpoint to verify API key is loaded
@auth_router.get("/test/config")
def test_config():
    """Test endpoint to verify configuration"""
    return {
        "api_key_set": bool(os.getenv("APPWRITE_API_KEY")),
        "project_id_set": bool(os.getenv("APPWRITE_PROJECT_ID")),
        "endpoint_set": bool(os.getenv("APPWRITE_ENDPOINT")),
        "jwt_secret_set": bool(os.getenv("JWT_SECRET_KEY"))
    }

# SIGNUP Endpoint
@auth_router.post("/account/signup")
def signup_user(
    name: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()]
):
    """Create new user account"""
    try:
        result = account.create(
            user_id=ID.unique(),
            email=email,
            password=password,
            name=name
        )
        return {"message": "User created successfully", "user_id": result["$id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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

# email verification
@auth_router.post("/auth/verify")
def send_verification_email():
    try:
        verification = account.create_verification(
            url="https://oyster-app-moqn5.ondigitalocean.app/")
        return {"message": "Verification email sent", "verification_id": verification["$id"]}
    except Exception as e:
        return {"error": str(e)}

# login 
@auth_router.post("/account/login")
def login_user(
    email: Annotated[EmailStr, Form(...)],
    password: Annotated[str, Form(...)]
):
    """
    Login user and create JWT token
    Validates credentials with Appwrite and generates custom JWT
    """
    try:
        # Validate credentials by creating session
        # This also gives us back user info
        session = account.create_email_password_session(
            email=email,
            password=password
        )
        
        user_id = session["userId"]
        print(f"DEBUG login: Session created for user {user_id}")
        
        # Create custom JWT with user info from session
        jwt_secret = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        payload = {
            "user_id": user_id,
            "email": email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7),
            "iat": datetime.datetime.utcnow()
        }
        jwt_token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        
        print(f"DEBUG login: JWT created, length: {len(jwt_token)}")
        
        return {
            "message": "Login successful",
            "user": {"id": user_id, "email": email},
            "session_id": session["$id"],
            "jwt": jwt_token,
            "secret": session.get("secret")  # Secret for session management
        }
    except Exception as e:
        print(f"DEBUG login ERROR: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Login failed: {str(e)}")

# get account user 
@auth_router.get("/account")
def get_account_user(authorization: Annotated[str, Header()]):
    # Requires:   with Bearer token (JWT from login)
    try:
        # Extract token from "Bearer <token>"
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        token = authorization.replace("Bearer ", "")
        
        # Decode JWT and get user_id
        _, user_id = get_user_client(token)
        
        # Get user details from Appwrite
        try:
            users_service = Users(client)
            user = users_service.get(user_id=user_id)
            user_email = user.get('email')
            print(f"DEBUG /account: Got user from Appwrite: {user_email}")
            
            # Fetch role from database
            try:
                user_docs = db.list_documents(
                    database_id=db_id,
                    collection_id=db_collection_id1,
                    queries=[Query.equal('email', user_email)]
                )
                
                if user_docs['total'] > 0:
                    db_user = user_docs['documents'][0]
                    user['role'] = db_user.get('role', 'superadmin')
                    user['phone'] = db_user.get('phone', '')
                    user['address'] = db_user.get('address', '')
                    user['department'] = db_user.get('department', '')
                    print(f"DEBUG /account: Added role from DB: {user['role']}")
                else:
                    user['role'] = 'superadmin'  # Default role
                    print(f"DEBUG /account: No DB record found, using default role")
            except Exception as db_error:
                print(f"DEBUG /account: DB query failed ({str(db_error)}), using default role")
                user['role'] = 'superadmin'
            
            return user
        except Exception as e:
            # Fallback: return user info from JWT if Users service fails
            print(f"DEBUG /account: Users service failed ({str(e)}), using JWT data")
            jwt_secret = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            return {
                "$id": payload.get("user_id"),
                "email": payload.get("email"),
                "name": payload.get("name", ""),
                "role": "superadmin",  # Default role
                "registration": ""
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG /account ERROR: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# get session
@auth_router.get("/account/sessions/{sessionId}")
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

# update email 
@auth_router.patch("/account/email")
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
@auth_router.patch("/account/name")
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
@auth_router.patch("/account/password")
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
@auth_router.patch("/account/phone")
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


# delete account user 
@auth_router.delete("/account/identities/{identityId}")
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
@auth_router.delete("/account/sessions")
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