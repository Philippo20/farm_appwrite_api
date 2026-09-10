from fastapi import APIRouter, Form, Header, HTTPException, Depends, Request
from appwrite.services.account import Account
from appwrite.services.users import Users
from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.id import ID
from main import client, db_id, db_collection_id1
from db import db
from appwrite.query import Query
from pydantic import EmailStr
from typing import Annotated, Optional
from enum import Enum
import smtplib
import os
from dotenv import load_dotenv
import jwt
import datetime
import logging
import uuid
import json

load_dotenv()


auth_router = APIRouter(tags=["Auth"])

account = Account(client)

EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_PORT= int(os.getenv("EMAIL_PORT"))
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_SECURITY = os.getenv("EMAIL_SECURITY")


async def auth_middleware(request: Request, call_next):
    """Validates Appwrite JWT token from Authorization header"""

    # Allow public routes (register, login)
    public_paths = [
        "/auth/register",
        "/auth/login",
        "/docs",
        "/openapi.json"
    ]
    if request.url.path in public_paths:
        return await call_next(request)

    # Read Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.replace("Bearer ", "").strip()

    # Validate the JWT using Appwrite
    try:
        client = Client()
        client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
        client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        client.set_jwt(token)

        account = Account(client)
        user = account.get()  # If invalid JWT → Appwrite throws error

        # Attach user to request.state
        request.state.user = user

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired JWT: {str(e)}")

    return await call_next(request)


def get_server_client():
    client = Client()
    client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
    client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
    client.set_key(os.getenv("APPWRITE_API_KEY"))
    client.set_self_signed(
        os.getenv("APPWRITE_SELF_SIGNED", "false").strip().lower() == "true"
    )
    return client

def get_user_client_from_jwt(jwt_token: str) -> Client:
    """Client authenticated with a JWT (user context)."""
    client = Client()
    client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
    client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
    client.set_jwt(jwt_token)
    client.set_self_signed(
        os.getenv("APPWRITE_SELF_SIGNED", "false").strip().lower() == "true"
    )
    return client

# Helper function to create user-specific client with session ID
def get_session_client(session_id: str) -> Client:
    """Create Appwrite client with session ID"""
    user_client = Client()
    user_client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
    user_client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
    user_client.set_session(session_id)
    return user_client

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
    # Create new user account
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

login_logger = logging.getLogger("uvicorn.error")


def _login_diagnostics(email):
    """Read-only account linkage checks. Never return these to anonymous clients."""
    result = {}
    profile_id = None
    try:
        profiles = db.list_documents(database_id=db_id, collection_id=db_collection_id1,
                                     queries=[Query.equal("email", email), Query.limit(2)])
        rows = profiles.get("documents", [])
        result["profile_count"] = profiles.get("total", len(rows))
        if rows:
            profile_id = rows[0].get("$id")
            result["profile_active"] = str(rows[0].get("status", "Active")).strip().lower() == "active"
    except Exception:
        result["profile_lookup_failed"] = True
    try:
        accounts = Users(get_server_client()).list(queries=[Query.equal("email", email), Query.limit(2)])
        rows = accounts.get("users", [])
        result["auth_account_count"] = accounts.get("total", len(rows))
        if rows:
            result["auth_enabled"] = rows[0].get("status") is True
            result["email_verified"] = rows[0].get("emailVerification") is True
            result["profile_auth_ids_match"] = profile_id is not None and profile_id == rows[0].get("$id")
    except Exception:
        result["auth_lookup_failed"] = True
    return result


# login
@auth_router.post("/account/login")
def login_user(
    email: Annotated[EmailStr, Form(...)], 
    password: Annotated[str, Form(...)]):
    email = str(email).strip().lower()
    reference = uuid.uuid4().hex[:12]
    stage = "create_password_session"

    def reject(code, reason, message, upstream_code=None, diagnose=False):
        details = _login_diagnostics(email) if diagnose else {}
        # Do not log raw upstream exceptions, requests, profiles, or credentials.
        login_logger.warning("login_rejected %s", json.dumps({
            "reference": reference, "stage": stage, "reason": reason,
            "http_status": code, "upstream_status": upstream_code, **details,
        }))
        return HTTPException(code, f"{message} Support reference: {reference}.")

    try:
        # Create session using SERVER KEY
        server_client = get_server_client()
        server_account = Account(server_client)

        session = server_account.create_email_password_session(
            email=email,
            password=password
        )

        stage = "initialize_user_session"
        # Create a USER client using the session cookie
        user_client = Client()
        user_client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
        user_client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        user_client.set_self_signed(
            os.getenv("APPWRITE_SELF_SIGNED", "false").strip().lower() == "true"
        )

        # Appwrite stores session in cookies -> pass it manually
        session_secret = session["secret"]
        user_client.set_session(session_secret)

        user_account = Account(user_client)

        stage = "load_profile"
        profile_result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id1,
            queries=[Query.equal("email", email)]
        )
        profile = profile_result["documents"][0] if profile_result["total"] > 0 else None
        if not profile:
            raise reject(403, "profile_missing", "Login blocked: user profile was not found.")

        user_status = profile.get("status", "Active")
        if str(user_status).strip().lower() != "active":
            raise reject(403, "profile_not_active", "Login blocked: your account is not active.")

        # Now create JWT using user session client (NOT server key)
        stage = "create_jwt"
        jwt_result = user_account.create_jwt()

        return {
            "message": "Login successful",
            "session_id": session["$id"],
            "jwt": jwt_result["jwt"],
            "user": profile
        }

    except HTTPException:
        raise
    except AppwriteException as error:
        if getattr(error, "type", "") == "user_invalid_credentials":
            raise reject(401, "user_invalid_credentials", "Email or password was not accepted. Account approval does not change your password.", error.code, diagnose=True) from error
        if getattr(error, "type", "") == "user_blocked":
            raise reject(403, "user_blocked", "Your account is not active.", error.code, diagnose=True) from error
        if error.code == 429:
            raise reject(429, "rate_limited", "Too many sign-in attempts. Please try again later.", error.code) from error
        raise reject(503, "upstream_service_error", "Sign-in service is temporarily unavailable. Please try again.", error.code) from error
    except Exception as error:
        raise reject(503, "internal_error", "Sign-in service is temporarily unavailable. Please try again.") from error

# email verification
@auth_router.post("/auth/verifications/email")
def send_verification_email(authorization: Optional[str] = Header(None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header missing")
        
        token = authorization.replace("Bearer ", "").strip()
        try:
            user_client = get_user_client_from_jwt(token)
            account = Account(user_client)
            result = account.create_verification(url="https://oyster-app-moqn5.ondigitalocean.app/#/verify")
            return {"message": "Verification email sent", "data": result}
        except AppwriteException as e:
            raise HTTPException(status_code=e.code or 400, detail=e.message)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        # client = Client()
        # # client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
        # client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        # # client.set_jwt(token)  # VERY IMPORTANT

        # account = Account(client)
        # verification = account.create_verification(
        #     url="https://oyster-app-moqn5.ondigitalocean.app/")
        # return {"message": "Verification email sent", "verification_id": verification["$id"]}
        # except Exception as e:
        #     return {"error": str(e)}

# create password recovery
@auth_router.post("/account/recovery")
def create_password_recovery(email: Annotated[EmailStr, Form()]):
    try:
        client = Client()
        client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
        client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        client.set_session('')

        account=Account(client)
        result = account.create_recovery(
                    email = email,
                    url = "https://oyster-app-moqn5.ondigitalocean.app/#/reset-password"
        )
        return {"message": "Verification email sent", "verification_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# Confirm verification
@auth_router.get("/verify/confirm")
def confirm_verification(user_id: str, secret: str):
    try:
        server_client = get_server_client()
        account = Account(server_client)
        result = account.update_verification(user_id=user_id, secret=secret)
        return {"message": "Verification confirmed", "data": result}
    except AppwriteException as e:
        raise HTTPException(status_code=e.code or 400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# update email verification
@auth_router.put("/account/verifications/email")
def update_email_verification(user_id:str, secret_id:str):
    try:
        client = Client()
        client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
        client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        client.set_session('')

        account = Account(client)
        verification= account.update_verification(
            user_id= user_id,
            secret=secret_id
        )
        return {"message": "Verification email updated", "verification_id": verification["$id"]}
    except Exception as e:
        return {"error": str(e)}

# Update password recovery (confirmation)
@auth_router.put("/account/recovery")
def update_password_recovery(user_id:str, secret_id:str, password:str):
    try:
        client = Client()
        client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
        client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
        client.set_session('')

        account = Account(client)
        result = account.update_recovery(
            user_id = user_id,
            secret = secret_id,
            password = password
        )
        return {"message": "Password changed successfully", "verification_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

# update email 
@auth_router.patch("/account/email")
def update_email(
    email: Annotated[EmailStr, Form(...)],
    password: Annotated[str, Form(...)],
    authorization: Annotated[str, Header()]
):
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client_from_jwt(jwt_token)
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
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client_from_jwt(jwt_token)
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
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client_from_jwt(jwt_token)
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
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        jwt_token = authorization.replace("Bearer ", "")
        user_client = get_user_client_from_jwt(jwt_token)
        user_account = Account(user_client)
        
        result = user_account.update_phone(phone=phone, password=password)
        return {"message": "Phone number updated successfully!", "user_id": result["$id"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update phone: {str(e)}")

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.replace("Bearer ", "").strip()
    try:
        user_client = get_user_client_from_jwt(token)
        account = Account(user_client)
        user = account.get()
        return user
    except AppwriteException as e:
        raise HTTPException(status_code=e.code or 401, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@auth_router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"user": user}

# logout
@auth_router.post("/logout")
def logout(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.replace("Bearer ", "").strip()
    try:
        user_client = get_user_client_from_jwt(token)
        account = Account(user_client)
        actor = account.get()
        claims = jwt.decode(token, options={"verify_signature": False})
        session_id = claims.get("sessionId")
        if not session_id:
            raise HTTPException(401, "Please sign in again.")
        Users(get_server_client()).delete_session(user_id=actor["$id"], session_id=session_id)
        return {"message": "Logged out"}
    except HTTPException:
        raise
    except AppwriteException as e:
        raise HTTPException(status_code=e.code or 400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@auth_router.post("/account/session")
def refresh_session(authorization: str = Header(default="")):
    """Refresh a verified session; disclose only the public inactivity policy."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please sign in again.")
    token = authorization[7:]
    try:
        actor = Account(get_user_client_from_jwt(token)).get()
    except AppwriteException as error:
        if error.code in (401, 403):
            raise HTTPException(401, "Your session has expired. Please sign in again.") from error
        raise HTTPException(503, "Unable to verify your session. Try again.") from error
    try:
        # Appwrite verified this exact token before its claims are inspected.
        claims = jwt.decode(token, options={"verify_signature": False})
        session_id = claims.get("sessionId")
        if not session_id:
            raise HTTPException(401, "Please sign in again.")
        users = Users(get_server_client())
        sessions = users.list_sessions(user_id=actor["$id"])
        session = next((item for item in sessions.get("sessions", [])
                        if item.get("$id") == session_id), None)
        if session is None:
            raise HTTPException(401, "Your session has expired. Please sign in again.")
        from datetime import timezone
        if datetime.datetime.fromisoformat(session["expire"].replace("Z", "+00:00")) <= datetime.datetime.now(timezone.utc):
            raise HTTPException(401, "Your session has expired.")
        profiles = db.list_documents(database_id=db_id, collection_id=db_collection_id1,
                                     queries=[Query.equal("email", actor["email"])])["documents"]
        if not profiles or profiles[0].get("status", "Active").lower() != "active":
            raise HTTPException(403, "Your account is not active.")
        from routes.r18_system_config import _get_or_create_config
        config = _get_or_create_config()
        renewed = users.create_jwt(user_id=actor["$id"], session_id=session_id, duration=900)
        return {"jwt": renewed["jwt"], "session_timeout": config.get("session_timeout") or 30,
                "session_idle_warning_minutes": config.get("session_idle_warning_minutes") or 5}
    except HTTPException:
        raise
    except AppwriteException as error:
        # Only a missing session proves revocation here. Authentication already
        # succeeded above; permission failures in these server-key operations
        # are configuration errors, not an expired user session.
        if error.code == 404 and getattr(error, "type", "") == "user_session_not_found":
            raise HTTPException(401, "Your session has expired. Please sign in again.") from error
        raise HTTPException(503, "Unable to verify your session. Try again.") from error
