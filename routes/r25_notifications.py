from datetime import datetime, timezone
from typing import Annotated

from appwrite.id import ID
from fastapi import APIRouter, HTTPException, Query as FastAPIQuery

from db import db
from main import db_collection_id25, db_id

collection25_router = APIRouter(tags=["Notifications"])


def create_notification(
    *,
    recipient_id: str,
    recipient_name: str,
    title: str,
    message: str,
    notification_type: str = "system",
    priority: str = "normal",
    related_task_id: str = "",
):
    data = {
        "notification_id": ID.unique(),
        "recipient_id": recipient_id,
        "recipient_name": recipient_name,
        "title": title,
        "message": message,
        "type": notification_type,
        "priority": priority
        if priority in {"low", "normal", "high", "urgent"}
        else "normal",
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if related_task_id:
        data["related_task_id"] = related_task_id
    return db.create_document(
        database_id=db_id,
        collection_id=db_collection_id25,
        document_id=ID.unique(),
        data=data,
    )


@collection25_router.get("/notifications")
def get_notifications(recipient_id: Annotated[str, FastAPIQuery()]):
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id25,
        )
        documents = [
            document
            for document in result["documents"]
            if document.get("recipient_id") == recipient_id
        ]
        return {"count": len(documents), "users": documents}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection25_router.patch("/notifications/read-all")
def mark_all_notifications_as_read(recipient_id: Annotated[str, FastAPIQuery()]):
    """Persist the read state for every notification owned by one recipient."""
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id25,
        )
        documents = [
            document
            for document in result["documents"]
            if document.get("recipient_id") == recipient_id
        ]
        for document in documents:
            db.update_document(
                database_id=db_id,
                collection_id=db_collection_id25,
                document_id=document["$id"],
                data={"is_read": True},
            )
        return {"count": len(documents), "updated": True}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection25_router.patch("/notifications/{notification_id}/read")
def mark_notification_as_read(notification_id: str):
    """Persist one notification's read state."""
    try:
        document = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id25,
            document_id=notification_id,
            data={"is_read": True},
        )
        return {"updated": True, "notification": document}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
