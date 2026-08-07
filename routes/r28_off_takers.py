from enum import Enum
from typing import Annotated

from appwrite.id import ID
from db import db
from fastapi import APIRouter, Form, HTTPException
from main import db_collection_id28, db_id

from audit_utils import write_audit

collection28_router = APIRouter(tags=["Off-takers"])


class OffTakerStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PROSPECT = "Prospect"


def _data(name, business_type, contact_person, phone, email, location, status, notes, created_by):
    return {
        "name": name.strip(),
        "business_type": business_type.strip(),
        "contact_person": contact_person.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "location": location.strip(),
        "status": status.value,
        "notes": notes.strip(),
        "created_by": created_by.strip(),
    }


@collection28_router.get("/off-takers")
def get_off_takers():
    try:
        result = db.list_documents(database_id=db_id, collection_id=db_collection_id28)
        return {"count": len(result["documents"]), "off_takers": result["documents"]}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection28_router.post("/off-takers")
def create_off_taker(
    name: Annotated[str, Form()],
    business_type: Annotated[str, Form()] = "",
    contact_person: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    location: Annotated[str, Form()] = "",
    status: Annotated[OffTakerStatus, Form()] = OffTakerStatus.ACTIVE,
    notes: Annotated[str, Form()] = "",
    created_by: Annotated[str, Form()] = "",
):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Off-taker name is required")
    payload = _data(name, business_type, contact_person, phone, email, location, status, notes, created_by)
    try:
        document = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id28,
            document_id=ID.unique(),
            data=payload,
        )
        write_audit(
            action_type="Create",
            collection_name="Off-takers",
            performed_by_id=created_by or "system",
            performed_by_role="sales",
            action_details=f"Created off-taker {name}",
            new_data=payload,
        )
        return {"message": "Off-taker created successfully", "off_taker": document}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection28_router.put("/off-takers/{off_taker_id}")
def update_off_taker(
    off_taker_id: str,
    name: Annotated[str, Form()],
    business_type: Annotated[str, Form()] = "",
    contact_person: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    location: Annotated[str, Form()] = "",
    status: Annotated[OffTakerStatus, Form()] = OffTakerStatus.ACTIVE,
    notes: Annotated[str, Form()] = "",
    created_by: Annotated[str, Form()] = "",
):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Off-taker name is required")
    try:
        previous = db.get_document(database_id=db_id, collection_id=db_collection_id28, document_id=off_taker_id)
        payload = _data(name, business_type, contact_person, phone, email, location, status, notes, created_by)
        document = db.update_document(
            database_id=db_id, collection_id=db_collection_id28, document_id=off_taker_id, data=payload
        )
        write_audit(
            action_type="Update",
            collection_name="Off-takers",
            performed_by_id=created_by or "system",
            performed_by_role="sales",
            action_details=f"Updated off-taker {name}",
            previous_data=previous,
            new_data=payload,
        )
        return {"message": "Off-taker updated successfully", "off_taker": document}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection28_router.delete("/off-takers/{off_taker_id}")
def delete_off_taker(off_taker_id: str):
    try:
        previous = db.get_document(database_id=db_id, collection_id=db_collection_id28, document_id=off_taker_id)
        db.delete_document(database_id=db_id, collection_id=db_collection_id28, document_id=off_taker_id)
        write_audit(
            action_type="Delete",
            collection_name="Off-takers",
            performed_by_id=previous.get("created_by", "system"),
            performed_by_role="sales",
            action_details=f"Deleted off-taker {previous.get('name', off_taker_id)}",
            previous_data=previous,
        )
        return {"message": "Off-taker deleted successfully"}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
