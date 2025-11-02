from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from datetime import datetime, date
from main import db_id, db_collection_id14
from db import db
from appwrite.id import ID
from appwrite.query import Query


collection14_router = APIRouter(tags=["Logs"])

@collection14_router.post("/logs/info")
def register_logs_info(
        action: Annotated[str, Form()],
        timestamp: Annotated[date, Form(...)]
        ):
    logs_info = {
        "userID": ID.unique(),
        "action": action,
        "timestamp": timestamp.isoformat(),
    }

    log_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id14,
        document_id=ID.unique(),
        data= logs_info
    )

    return {
        "message": "Log information registered successfully",
        "logs_info_id": log_create["$id"]
    }

@collection14_router.get("/logs")
def get_all_logs():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id14
        )

        # Extract the list of users
        log_users = result["documents"]

        return {
            "count": len(log_users),
            "users": log_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection14_router.get("/logs/{logs_id}")
def get_log_info(logs_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id14,
            document_id= logs_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection14_router.put("/logs/{logs_id}")
def update_log(
    logs_id:str,
    userID: Annotated[str, Form()],
    action: Annotated[str, Form()],
    timestamp: Annotated[date, Form(...)]):

    try:
        # Perform update
        updated_log_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id14,
            document_id=logs_id,
            data={"userID": userID,
                  "action": action,
                  "timestamp": timestamp.isoformat()
            },
            permissions=[]
        )
        return {"message": "Logs info updated successfully", "user": updated_log_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection14_router.delete("/logs/{logs_id}")
def delete_logs(logs_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id14, 
            document_id=logs_id)
        return {"message": f"User with ID {logs_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))