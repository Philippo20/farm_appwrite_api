from fastapi import APIRouter, Form, HTTPException, Header, Depends
from appwrite.services.account import Account
from appwrite.id import ID
from appwrite.query import Query
from typing import Annotated
from pydantic import EmailStr
from appwrite.exception import AppwriteException
from appwrite.client import Client
import os
from dotenv import load_dotenv

load_dotenv()

# client = Client()

# client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
# client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
# client.set_key(os.getenv("APPWRITE_API_KEY"))
# # client.set_jwt(jwt_token)

# client.set_self_signed(True)

# account = Account(client)

auth_router = APIRouter(tags=["Auth1"])

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
client.set_key(os.getenv("APPWRITE_API_KEY"))
client.set_self_signed(True)

account = Account(client)

try:
    print(account.list_sessions())  # This should now succeed ✅
except Exception as e:
    print("Error:", e)

def get_server_client():
    client = Client()
    client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
    client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
    client.set_key(os.getenv("APPWRITE_API_KEY"))
    client.set_self_signed(True)
    return client

# ✅ Initialize Appwrite Client for user-side tasks (uses JWT)
def get_user_client():
    client = Client()
    client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
    client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
    # client.set_jwt(jwt_token)
    client.set_self_signed(True)
    return client

print("Endpoint:", os.getenv("APPWRITE_PROJECT_ID"))
print("Project:", os.getenv("APPWRITE_ENDPOINT"))

# SIGNUP Endpoint
@auth_router.post("/account/signup")
def signup_user(
    name: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form()]

):
    try:
        account = Account(get_server_client())
        result = account.create(
            user_id=ID.unique(),
            email=email,
            password= password,
            name=name
        )
        return {"message": "User created successfully", "user_id": result["$id"]}
    except Exception as e:
        return {"error": str(e)}

@auth_router.get("/account/jwt/confirm")
def confirm_verification(user_id: str, secret: str):
    try:
        account = Account(get_server_client())
        result = account.update_verification(user_id=user_id, secret=secret)
        return {"message": "User verified successfully!", "data": result}
    except AppwriteException as e:
        raise HTTPException(status_code=e.code or 400, detail=e.message)


@auth_router.get("/account")
def get_account(Authorization: str = Header(None)):
    """Get the logged-in user's Appwrite account using JWT"""
    try:
        if not Authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        if not Authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid Authorization format")

        jwt_token = Authorization.replace("Bearer ", "").strip()

        account = Account(get_user_client(jwt_token))
        user = account.get()
        return {"user": user}

    except AppwriteException as e:
        raise HTTPException(status_code=e.code or 400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# login 
# @auth_router.post("/account/login")
# def login_user(
#     email: Annotated[EmailStr, Form(...)],
#     password: Annotated[str, Form(...)]
# ):
#     try:
#         account = Account(get_user_client())
#         session = account.create_email_password_session(
#             email=email,
#             password=password
#         )
#         # Create JWT token from the session
#         jwt_result = account.create_jwt()
        
#         return {
#             "message": "Login successful",
#             "session_id": session["$id"],
#             "jwt": jwt_result.get("jwt"),  # Return JWT token
#             "secret": jwt_result.get("secret")  # Secret for session management
#         }
#     except AppwriteException as e:
#         raise HTTPException(status_code=400, detail=f"Appwrite error: {e.message}")
#     except Exception as e:
#         raise HTTPException(status_code=401, detail=f"Login failed: {str(e)}")

# -----------------------------
# ✅ Send Email Verification Link
# -----------------------------
@auth_router.post("/account/verify/jwt")
def verify_user():
    try:
        account = Account(get_server_client())
        result = account.create_verification(
            url="https://goldfish-app-pet66.ondigitalocean.app/"
        )
        return {"message": "Verification email sent successfully", "data": result}
    except AppwriteException as e:
        raise HTTPException(status_code=e.code or 400, detail=e.message)



def get_appwrite_client():
    return Client().set_endpoint(os.getenv("APPWRITE_ENDPOINT")).set_project(os.getenv("APPWRITE_PROJECT_ID"))

@auth_router.post("/account/login")
def login_user(
    email: Annotated[EmailStr, Form(...)],
    password: Annotated[str, Form(...)]
):
    try:
        # Step 1: Create session
        client = get_appwrite_client()
        account = Account(client)
        session = account.create_email_password_session(email=email, password=password)

        # Step 2: Use session secret for authenticated client
        user_client = get_appwrite_client().set_session(session["secret"])
        user_account = Account(user_client)
        jwt_result = user_account.create_jwt()

        # Step 3: Return JWT
        return {
            "message": "Login successful",
            "session_id": session["$id"],
            "jwt": jwt_result.get("jwt"),
            "secret": session.get("secret")
        }

    except AppwriteException as e:
        raise HTTPException(status_code=400, detail=f"Appwrite error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Login failed: {str(e)}")