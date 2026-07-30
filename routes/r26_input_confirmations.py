from datetime import datetime, timezone
from typing import Annotated

from appwrite.id import ID
from fastapi import APIRouter, Form, HTTPException, Query

from audit_utils import write_audit
from db import db
from main import db_collection_id26, db_id
from routes.r25_notifications import create_notification

collection26_router = APIRouter(tags=["Input Confirmations"])
VALID_STATUSES = {"Pending", "Received", "Confirmed"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _input_code():
    return f"INP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"


def _documents():
    return db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id26,
    ).get("documents", [])


@collection26_router.get("/input-confirmations")
def get_input_confirmations(
    caretaker_id: Annotated[str | None, Query()] = None,
    farm_id: Annotated[str | None, Query()] = None,
):
    try:
        documents = _documents()
        if caretaker_id:
            documents = [
                document
                for document in documents
                if document.get("caretaker_id") == caretaker_id
            ]
        if farm_id:
            documents = [
                document for document in documents if document.get("farm_id") == farm_id
            ]
        documents.sort(
            key=lambda document: document.get("requested_at", ""), reverse=True
        )
        return {"count": len(documents), "users": documents}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection26_router.post("/input-confirmations/info")
def create_input_confirmation(
    farm_id: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    item: Annotated[str, Form()],
    quantity: Annotated[str, Form()],
    requested_by_id: Annotated[str, Form()],
    requested_by_name: Annotated[str, Form()],
    caretaker_id: Annotated[str, Form()],
    caretaker_name: Annotated[str, Form()],
    requested_at: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
):
    if not farm_id.strip() or not item.strip() or not quantity.strip():
        raise HTTPException(status_code=400, detail="Farm, item, and quantity are required")
    now = _now()
    data = {
        "input_id": _input_code(),
        "farm_id": farm_id.strip(),
        "farm_name": farm_name.strip(),
        "item": item.strip(),
        "quantity": quantity.strip(),
        "requested_by_id": requested_by_id.strip(),
        "requested_by_name": requested_by_name.strip(),
        "caretaker_id": caretaker_id.strip(),
        "caretaker_name": caretaker_name.strip(),
        "status": "Pending",
        "notes": notes.strip(),
        "requested_at": requested_at.strip() or now,
        "created_at": now,
        "updated_at": now,
    }
    try:
        created = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id26,
            document_id=ID.unique(),
            data=data,
        )
        write_audit(
            action_type="Create",
            collection_name="Input Confirmations",
            performed_by_id=requested_by_id,
            performed_by_role="farm_manager",
            action_details=f"Created input request {data['input_id']} for {caretaker_name}",
            new_data=data,
        )
        try:
            create_notification(
                recipient_id=caretaker_id,
                recipient_name=caretaker_name,
                title="New input request",
                message=f"{requested_by_name} requested {quantity} of {item} for {farm_name}.",
                notification_type="inventory",
                priority="normal",
            )
        except Exception:
            pass
        return {"message": "Input request created successfully", "input": created}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection26_router.patch("/input-confirmations/{input_doc_id}/status")
def update_input_confirmation_status(
    input_doc_id: str,
    status: Annotated[str, Form()],
    caretaker_id: Annotated[str, Form()] = "",
    caretaker_name: Annotated[str, Form()] = "",
):
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid input confirmation status")
    try:
        previous = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id26,
            document_id=input_doc_id,
        )
        now = _now()
        data = {"status": status, "updated_at": now}
        if status == "Received":
            data["received_at"] = now
        if status == "Confirmed":
            data["confirmed_at"] = now
        updated = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id26,
            document_id=input_doc_id,
            data=data,
        )
        actor_id = caretaker_id or previous.get("caretaker_id", "")
        actor_name = caretaker_name or previous.get("caretaker_name", "Caretaker")
        write_audit(
            action_type="Update",
            collection_name="Input Confirmations",
            performed_by_id=actor_id,
            performed_by_role="caretaker",
            action_details=f"Changed input {previous.get('input_id', input_doc_id)} to {status}",
            previous_data=previous,
            new_data=data,
        )
        requester_id = previous.get("requested_by_id", "")
        if requester_id and requester_id != actor_id:
            try:
                create_notification(
                    recipient_id=requester_id,
                    recipient_name=previous.get("requested_by_name", ""),
                    title="Input request updated",
                    message=(
                        f"{actor_name} marked {previous.get('item', 'the input request')} "
                        f"as {status} on {previous.get('farm_name', 'the farm')} ."
                    ),
                    notification_type="inventory",
                    priority="normal",
                )
            except Exception:
                pass
        return {"message": "Input confirmation updated successfully", "input": updated}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
