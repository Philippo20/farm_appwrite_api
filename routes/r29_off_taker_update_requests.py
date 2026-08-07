import json
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from appwrite.id import ID
from fastapi import APIRouter, Form, HTTPException

from audit_utils import write_audit
from db import db
from main import db_collection_id1, db_collection_id28, db_collection_id29, db_id
from routes.r25_notifications import create_notification

collection29_router = APIRouter(tags=["Off-taker update requests"])


class RequestStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _notify_sales_roles(title: str, message: str, *, exclude_id: str = ""):
    try:
        users = db.list_documents(database_id=db_id, collection_id=db_collection_id1)["documents"]
        for user in users:
            role = str(user.get("role", user.get("user_role", ""))).lower().replace("_", " ")
            if "sales manager" not in role and "sales personnel" not in role and "sales person" not in role:
                continue
            recipient_id = str(user.get("$id", user.get("id", "")))
            if not recipient_id or recipient_id == exclude_id:
                continue
            create_notification(
                recipient_id=recipient_id,
                recipient_name=str(user.get("name", user.get("email", "Sales user"))),
                title=title,
                message=message,
                notification_type="sales",
                priority="normal",
            )
    except Exception:
        # A notification failure must not roll back the business transaction.
        pass


@collection29_router.get("/off-taker-update-requests")
def get_requests(status: str | None = None):
    try:
        result = db.list_documents(database_id=db_id, collection_id=db_collection_id29)
        documents = result["documents"]
        if status:
            documents = [item for item in documents if item.get("status") == status]
        return {"count": len(documents), "off_taker_update_requests": documents}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection29_router.post("/off-taker-update-requests")
def create_request(
    off_taker_id: Annotated[str, Form()],
    proposed_data: Annotated[str, Form()],
    reason: Annotated[str, Form()],
    requested_by_id: Annotated[str, Form()],
    requested_by_name: Annotated[str, Form()],
):
    if not reason.strip():
        raise HTTPException(status_code=400, detail="A reason for the update is required")
    try:
        proposal = json.loads(proposed_data)
        if not isinstance(proposal, dict):
            raise ValueError("proposal must be an object")
        db.get_document(database_id=db_id, collection_id=db_collection_id28, document_id=off_taker_id)
        payload = {
            # Kept for compatibility with the first provisioned version of
            # collection 29, which created a required legacy attribute.
            "key": "",
            "off_taker_id": off_taker_id.strip(),
            "proposed_data": json.dumps(proposal),
            "reason": reason.strip(),
            "requested_by_id": requested_by_id.strip(),
            "requested_by_name": requested_by_name.strip(),
            "status": RequestStatus.PENDING.value,
            "requested_at": _now(),
        }
        document = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id29,
            document_id=ID.unique(),
            data=payload,
        )
        write_audit(
            action_type="Create",
            collection_name="Off-taker update requests",
            performed_by_id=requested_by_id or "system",
            performed_by_role="sales_personnel",
            action_details=f"Requested off-taker update: {reason.strip()}",
            new_data=payload,
        )
        _notify_sales_roles(
            "Off-taker update awaiting approval",
            f"{requested_by_name} requested an update. Reason: {reason.strip()}",
            exclude_id=requested_by_id,
        )
        return {"message": "Update request submitted for manager approval", "request": document}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@collection29_router.put("/off-taker-update-requests/{request_id}/review")
def review_request(
    request_id: str,
    status: Annotated[RequestStatus, Form()],
    reviewed_by_id: Annotated[str, Form()],
    reviewed_by_name: Annotated[str, Form()],
    review_notes: Annotated[str, Form()] = "",
):
    if status not in [RequestStatus.APPROVED, RequestStatus.REJECTED]:
        raise HTTPException(status_code=400, detail="Review status must be Approved or Rejected")
    try:
        request = db.get_document(database_id=db_id, collection_id=db_collection_id29, document_id=request_id)
        if request.get("status") != RequestStatus.PENDING.value:
            raise HTTPException(status_code=409, detail="This request has already been reviewed")
        updated = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id29,
            document_id=request_id,
            data={
                "status": status.value,
                "reviewed_by_id": reviewed_by_id.strip(),
                "reviewed_by_name": reviewed_by_name.strip(),
                "review_notes": review_notes.strip(),
                "reviewed_at": _now(),
            },
        )
        off_taker = None
        if status == RequestStatus.APPROVED:
            proposal = json.loads(request.get("proposed_data", "{}"))
            off_taker = db.get_document(
                database_id=db_id,
                collection_id=db_collection_id28,
                document_id=request["off_taker_id"],
            )
            proposal.pop("$id", None)
            proposal.pop("$createdAt", None)
            proposal.pop("$updatedAt", None)
            off_taker = db.update_document(
                database_id=db_id,
                collection_id=db_collection_id28,
                document_id=request["off_taker_id"],
                data=proposal,
            )
        write_audit(
            action_type="Approve" if status == RequestStatus.APPROVED else "Reject",
            collection_name="Off-taker update requests",
            performed_by_id=reviewed_by_id or "system",
            performed_by_role="sales_manager",
            action_details=f"{status.value} off-taker update request {request_id}",
            previous_data=request,
            new_data=updated,
        )
        requester_id = request.get("requested_by_id", "")
        requester_name = request.get("requested_by_name", "Sales Personnel")
        _notify_sales_roles(
            f"Off-taker update {status.value.lower()}",
            f"Your off-taker update request was {status.value.lower()} by {reviewed_by_name or 'Sales Manager'}.",
            exclude_id=requester_id,
        )
        if requester_id:
            try:
                create_notification(
                    recipient_id=requester_id,
                    recipient_name=requester_name,
                    title=f"Off-taker update {status.value.lower()}",
                    message=f"Your requested off-taker update was {status.value.lower()} by {reviewed_by_name or 'Sales Manager'}.",
                    notification_type="sales",
                    priority="normal",
                )
            except Exception:
                pass
        return {"message": f"Request {status.value.lower()}", "request": updated, "off_taker": off_taker}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
