from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from appwrite.id import ID
from appwrite.query import Query
from fastapi import APIRouter, Form, HTTPException, status as http_status

from audit_utils import write_audit
from db import db
from main import db_collection_id5, db_collection_id24, db_id
from routes.r25_notifications import create_notification

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
    planted_count: Annotated[str, Form()] = "",
    transplanted_count: Annotated[str, Form()] = "",
    harvested_count: Annotated[str, Form()] = "",
    harvest_weight_kg: Annotated[str, Form()] = "",
):
    if not farm_id.strip() or not farm_name.strip():
        raise HTTPException(status_code=400, detail="Farm is required")
    if has_issues and not issue_description.strip():
        raise HTTPException(status_code=400, detail="Issue description is required")

    batch = None
    batch_update = {}
    try:
        progress_values = {
            "total_seeds_nursed": _int_or_none(planted_count),
            "total_transplanted": _int_or_none(transplanted_count),
            "total_harvested": _int_or_none(harvested_count),
            "total_weight_kg": _float_or_none(harvest_weight_kg),
        }
    except ValueError as error:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch progress values must be valid numbers.",
        ) from error
    has_batch_update = any(value is not None for value in progress_values.values()) or (
        has_issues and bool(batch_id.strip())
    )
    if has_batch_update:
        if not batch_id.strip():
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Select a batch before recording batch progress.",
            )
        try:
            batch = db.get_document(
                database_id=db_id,
                collection_id=db_collection_id5,
                document_id=batch_id,
            )
        except Exception as error:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="The selected batch no longer exists.",
            ) from error

        if str(batch.get("farmID") or "").strip() != farm_id.strip():
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="The selected batch does not belong to this farm.",
            )
        assigned_id = str(batch.get("caretaker_id") or "").strip().lower()
        assigned_name = str(batch.get("caretaker_name") or "").strip().lower()
        actor_id = created_by.strip().lower()
        actor_name = created_by_name.strip().lower()
        if not assigned_id and not assigned_name:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Assign a caretaker to this batch before recording progress.",
            )
        if assigned_id and assigned_id not in {actor_id, actor_name} and (
            not assigned_name or assigned_name not in {actor_id, actor_name}
        ):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="This batch is not assigned to the current caretaker.",
            )

        for key, value in progress_values.items():
            if value is not None:
                if value < 0:
                    raise HTTPException(
                        status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Batch progress values cannot be negative.",
                    )
                batch_update[key] = value
        if has_issues:
            issue_summary = f"{issue_severity.value.title()}: {issue_description.strip()}"
            batch_update["technical_issues"] = issue_summary[:225]
        batch_update["updated_at"] = _now()

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
        if batch is not None and batch_update:
            try:
                db.update_document(
                    database_id=db_id,
                    collection_id=db_collection_id5,
                    document_id=batch_id,
                    data=batch_update,
                )
            except Exception:
                db.delete_document(
                    database_id=db_id,
                    collection_id=db_collection_id24,
                    document_id=created["$id"],
                )
                raise
            write_audit(
                action_type="Update",
                collection_name="Batches",
                performed_by_id=created_by,
                performed_by_role="caretaker",
                action_details=(
                    f"Updated batch {batch.get('batch_no', batch_id)} progress "
                    f"from farm record {record_id}"
                ),
                previous_data=batch,
                new_data=batch_update,
            )
            if has_issues and batch.get("farm_manager_id"):
                try:
                    create_notification(
                        recipient_id=str(batch.get("farm_manager_id")),
                        recipient_name=str(batch.get("farm_manager_name") or "Farm Manager"),
                        title="Batch issue reported",
                        message=(
                            f"{created_by_name} reported a {issue_severity.value} issue "
                            f"for {batch.get('batch_no', batch_number or 'a batch')}: "
                            f"{issue_description.strip()}"
                        )[:500],
                        notification_type="batch",
                        priority=(
                            "urgent"
                            if issue_severity == IssueSeverity.CRITICAL
                            else "high"
                            if issue_severity == IssueSeverity.HIGH
                            else "normal"
                        ),
                    )
                except Exception as notification_error:
                    print(f"Batch issue notification failed: {notification_error}")
        write_audit(
            action_type="Create",
            collection_name="Farm Records",
            performed_by_id=created_by,
            performed_by_role="caretaker",
            action_details=f"Created farm record {record_id} for {farm_name}",
            new_data=data,
        )
        return {
            "message": "Farm record submitted successfully",
            "record": created,
            "batch_updated": batch is not None,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
