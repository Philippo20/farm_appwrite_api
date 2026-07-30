from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from appwrite.id import ID
from appwrite.query import Query
from fastapi import APIRouter, Form, HTTPException, status as http_status

from audit_utils import write_audit
from db import db
from main import db_collection_id24, db_id

collection24_router = APIRouter(tags=["Farm Records"])


class IssueSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_code() -> str:
    return f"FR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def _float_or_none(value: str) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _int_or_none(value: str) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


@collection24_router.get("/farm-records")
def get_farm_records(limit: int = 100, offset: int = 0):
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id24,
            queries=[Query.limit(limit), Query.offset(offset)],
        )
        docs = result.get("documents", [])
        return {"count": len(docs), "users": docs}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection24_router.get("/farm-records/{record_doc_id}")
def get_farm_record(record_doc_id: str):
    try:
        return db.get_document(
            database_id=db_id,
            collection_id=db_collection_id24,
            document_id=record_doc_id,
        )
    except Exception as error:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )


@collection24_router.post("/farm-records/info")
def create_farm_record(
    farm_id: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    record_type: Annotated[str, Form()],
    record_date: Annotated[str, Form()],
    created_by: Annotated[str, Form()],
    created_by_name: Annotated[str, Form()],
    has_issues: Annotated[bool, Form()],
    issue_severity: Annotated[IssueSeverity, Form()] = IssueSeverity.NONE,
    batch_id: Annotated[str, Form()] = "",
    batch_number: Annotated[str, Form()] = "",
    temperature: Annotated[str, Form()] = "",
    humidity: Annotated[str, Form()] = "",
    ph: Annotated[str, Form()] = "",
    ec: Annotated[str, Form()] = "",
    light_intensity: Annotated[str, Form()] = "",
    plant_health: Annotated[str, Form()] = "",
    growth_stage: Annotated[str, Form()] = "",
    plant_count: Annotated[str, Form()] = "",
    observations: Annotated[str, Form()] = "",
    activities_performed: Annotated[str, Form()] = "",
    issue_description: Annotated[str, Form()] = "",
    notes: Annotated[str, Form()] = "",
):
    if not farm_id.strip() or not farm_name.strip():
        raise HTTPException(status_code=400, detail="Farm is required")
    if has_issues and not issue_description.strip():
        raise HTTPException(status_code=400, detail="Issue description is required")

    record_id = _record_code()
    now = _now()
    data = {
        "record_id": record_id,
        "farm_id": farm_id,
        "farm_name": farm_name,
        "batch_id": batch_id,
        "batch_number": batch_number,
        "record_type": record_type,
        "record_date": record_date,
        "created_by": created_by,
        "created_by_name": created_by_name,
        "plant_health": plant_health,
        "growth_stage": growth_stage,
        "observations": observations,
        "activities_performed": activities_performed,
        "has_issues": has_issues,
        "issue_description": issue_description,
        "issue_severity": issue_severity.value,
        "notes": notes,
        "created_at": now,
        "updated_at": now,
    }

    optional_numbers = {
        "temperature": _float_or_none(temperature),
        "humidity": _float_or_none(humidity),
        "ph": _float_or_none(ph),
        "ec": _float_or_none(ec),
        "light_intensity": _float_or_none(light_intensity),
        "plant_count": _int_or_none(plant_count),
    }
    data.update({key: value for key, value in optional_numbers.items() if value is not None})

    try:
        created = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id24,
            document_id=ID.unique(),
            data=data,
        )
        write_audit(
            action_type="Create",
            collection_name="Farm Records",
            performed_by_id=created_by,
            performed_by_role="caretaker",
            action_details=f"Created farm record {record_id} for {farm_name}",
            new_data=data,
        )
        return {"message": "Farm record submitted successfully", "record": created}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
