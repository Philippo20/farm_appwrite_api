from datetime import datetime, timezone
from typing import Annotated

from appwrite.id import ID
from fastapi import APIRouter, Depends, HTTPException, Query as FastAPIQuery
from appwrite.query import Query
from routes.messaging import current_member

from notification_preferences import preferences_for, delivery_options
from db import db
from notification_email import queue_notification_email
from main import db_collection_id25, db_id
from document_paging import list_all_documents

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
    saved = db.create_document(
        database_id=db_id,
        collection_id=db_collection_id25,
        document_id=ID.unique(),
        data=data,
    )

    queue_notification_email(recipient_id, title, message, notification_type)
    return saved


@collection25_router.get("/notifications")
def get_notifications(recipient_id: Annotated[str, FastAPIQuery()], actor=Depends(current_member)):
    if recipient_id != actor["$id"]:
        raise HTTPException(403, "You can only access your own notifications.")
    try:
        result = list_all_documents(db,
            database_id=db_id,
            collection_id=db_collection_id25,
            queries=[Query.equal("recipient_id", [actor["$id"]])],
        )
        documents = [
            document
            for document in result["documents"]
            if document.get("recipient_id") == recipient_id
        ]
        preferences = preferences_for(actor)
        return {"count": len(documents), "users": [
            {**item, **delivery_options(item.get('type', 'system'), preferences)} for item in documents]}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection25_router.patch("/notifications/read-all")
def mark_all_notifications_as_read(recipient_id: Annotated[str, FastAPIQuery()], actor=Depends(current_member)):
    if recipient_id != actor["$id"]:
        raise HTTPException(403, "You can only access your own notifications.")
    """Persist the read state for every notification owned by one recipient."""
    try:
        result = list_all_documents(db,
            database_id=db_id,
            collection_id=db_collection_id25,
            queries=[Query.equal("recipient_id", [actor["$id"]])],
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
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection25_router.patch("/notifications/{notification_id}/read")
def mark_notification_as_read(notification_id: str, actor=Depends(current_member)):
    """Persist one notification's read state."""
    try:
        owned = db.get_document(database_id=db_id, collection_id=db_collection_id25, document_id=notification_id)
        if owned.get('recipient_id') != actor['$id']:
            raise HTTPException(404, 'Notification not found.')
        document = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id25,
            document_id=notification_id,
            data={"is_read": True},
        )
        return {"updated": True, "notification": document}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
