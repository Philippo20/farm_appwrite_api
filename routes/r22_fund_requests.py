from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from appwrite.id import ID
from fastapi import APIRouter, Form, HTTPException, status as http_status

from audit_utils import write_audit
from db import db
from main import db_collection_id22, db_id

collection22_router = APIRouter(tags=["Fund Requests"])


class FundRequestStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    DISBURSED = "Disbursed"


class FundRequestCategory(str, Enum):
    OPERATIONS = "Operations"
    INPUTS = "Inputs"
    MAINTENANCE = "Maintenance"
    CAPITAL = "Capital"
    LABOUR = "Labour"
    TRANSPORT = "Transport"
    OTHER = "Other"


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_code() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"FR-{stamp}"


def _payload(
    *,
    farm_id: str,
    farm_name: str,
    requested_by_id: str,
    requested_by_name: str,
    amount: float,
    purpose: str,
    category: FundRequestCategory,
    priority: Priority,
    description: str,
    status: FundRequestStatus,
    currency: str,
    request_date: Optional[str] = None,
    approved_by_id: str = "",
    approved_by_name: str = "",
    approved_at: Optional[str] = None,
    decision_notes: str = "",
):
    data = {
        "farm_id": farm_id,
        "farm_name": farm_name,
        "requested_by_id": requested_by_id,
        "requested_by_name": requested_by_name,
        "amount": amount,
        "currency": currency,
        "purpose": purpose,
        "description": description,
        "category": category.value,
        "priority": priority.value,
        "status": status.value,
        "request_date": request_date or _now(),
        "approved_by_id": approved_by_id,
        "approved_by_name": approved_by_name,
        "decision_notes": decision_notes,
        "updated_at": _now(),
    }
    if approved_at:
        data["approved_at"] = approved_at
    return data


@collection22_router.post("/fund-requests/info")
def create_fund_request(
    farm_id: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    requested_by_id: Annotated[str, Form()],
    requested_by_name: Annotated[str, Form()],
    amount: Annotated[float, Form()],
    purpose: Annotated[str, Form()],
    category: Annotated[FundRequestCategory, Form()],
    priority: Annotated[Priority, Form()],
    description: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "GHS",
):
    request_id = _request_code()
    data = _payload(
        farm_id=farm_id,
        farm_name=farm_name,
        requested_by_id=requested_by_id,
        requested_by_name=requested_by_name,
        amount=amount,
        purpose=purpose,
        category=category,
        priority=priority,
        description=description,
        status=FundRequestStatus.PENDING,
        currency=currency,
    )
    data["request_id"] = request_id

    try:
        created = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id22,
            document_id=ID.unique(),
            data=data,
        )
        write_audit(
            action_type="Create",
            collection_name="Fund Requests",
            performed_by_id=requested_by_name or requested_by_id,
            performed_by_role="farm_manager",
            action_details=f"Created fund request {request_id}",
            new_data=data,
        )
        return {"message": "Fund request created successfully", "request": created}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection22_router.get("/fund-requests")
def get_fund_requests():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id22,
        )
        return {
            "count": len(result["documents"]),
            "users": result["documents"],
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection22_router.get("/fund-requests/{request_doc_id}")
def get_fund_request(request_doc_id: str):
    try:
        return db.get_document(
            database_id=db_id,
            collection_id=db_collection_id22,
            document_id=request_doc_id,
        )
    except Exception as error:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(error))


@collection22_router.put("/fund-requests/{request_doc_id}")
def update_fund_request(
    request_doc_id: str,
    farm_id: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    requested_by_id: Annotated[str, Form()],
    requested_by_name: Annotated[str, Form()],
    amount: Annotated[float, Form()],
    purpose: Annotated[str, Form()],
    category: Annotated[FundRequestCategory, Form()],
    priority: Annotated[Priority, Form()],
    status: Annotated[FundRequestStatus, Form()],
    description: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "GHS",
    approved_by_id: Annotated[str, Form()] = "",
    approved_by_name: Annotated[str, Form()] = "",
    decision_notes: Annotated[str, Form()] = "",
):
    try:
        previous = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id22,
            document_id=request_doc_id,
        )
        data = _payload(
            farm_id=farm_id,
            farm_name=farm_name,
            requested_by_id=requested_by_id,
            requested_by_name=requested_by_name,
            amount=amount,
            purpose=purpose,
            category=category,
            priority=priority,
            description=description,
            status=status,
            currency=currency,
            request_date=previous.get("request_date"),
            approved_by_id=approved_by_id,
            approved_by_name=approved_by_name,
            approved_at=_now() if status in [FundRequestStatus.APPROVED, FundRequestStatus.REJECTED, FundRequestStatus.DISBURSED] else previous.get("approved_at"),
            decision_notes=decision_notes,
        )
        updated = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id22,
            document_id=request_doc_id,
            data=data,
            permissions=[],
        )
        write_audit(
            action_type="Update",
            collection_name="Fund Requests",
            performed_by_id=requested_by_name or requested_by_id,
            performed_by_role="farm_manager",
            action_details=f"Updated fund request {previous.get('request_id', request_doc_id)}",
            previous_data=previous,
            new_data=data,
        )
        return {"message": "Fund request updated successfully", "request": updated}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection22_router.delete("/fund-requests/{request_doc_id}")
def delete_fund_request(request_doc_id: str):
    try:
        previous = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id22,
            document_id=request_doc_id,
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id22,
            document_id=request_doc_id,
        )
        write_audit(
            action_type="Delete",
            collection_name="Fund Requests",
            performed_by_id=previous.get("requested_by_name", previous.get("requested_by_id", "system")),
            performed_by_role="farm_manager",
            action_details=f"Deleted fund request {previous.get('request_id', request_doc_id)}",
            previous_data=previous,
        )
        return {"message": f"Fund request {request_doc_id} deleted successfully"}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
