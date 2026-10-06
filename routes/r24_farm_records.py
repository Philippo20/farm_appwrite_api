from farm_assignments import is_farm_caretaker
from routes.messaging import current_member
from user_roles import effective_profile
from production_planning import record_growth_plan, growth_stage_at
from water_record_values import water_record_values, water_parameter_values
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from appwrite.id import ID
from appwrite.query import Query
from fastapi import APIRouter, Depends, Form, HTTPException, Query as RequestQuery, status as http_status
from auth import get_current_user
from batch_record_access import can_review_records

from audit_utils import write_audit
from db import db
from main import db_collection_id1, db_collection_id2, db_collection_id3, db_collection_id5, db_collection_id7, db_collection_id24, db_id
from notification_email import queue_notification_email

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


def _ensure_batch_open(batch):
    complete = {"delivered", "complete", "completed"}
    closed = any(str(batch.get(key) or "").strip().casefold() in complete
                 for key in ("production_status", "delivery_status", "status"))
    references = {str(batch.get(key) or "").strip().casefold()
                  for key in ("$id", "id", "batch_id", "batch_no", "batch_number", "batch_code")}
    references.discard("")
    offset = 0
    while not closed and references:
        documents = db.list_documents(
            database_id=db_id, collection_id=db_collection_id7,
            queries=[Query.limit(100), Query.offset(offset)],
        ).get("documents", [])
        for item in documents:
            linked = any(str(item.get(key) or "").strip().casefold() in references
                         for key in ("batch_id", "batch_no", "batch_number", "batch_code"))
            received = str(item.get("delivery_status") or "").strip().casefold() == "delivered"
            received = received or str(item.get("status") or "").strip().casefold() in {
                "received", "packaging", "packaged", "sent to sales", "completed"
            }
            if linked and received:
                closed = True
                break
        if len(documents) < 100:
            break
        offset += len(documents)
    if closed:
        raise HTTPException(status_code=409, detail=(
            "This batch is complete after delivery to fulfillment. "
            "No further caretaker records can be taken."
        ))


@collection24_router.get("/batches/{batch_id}/caretaker-records")
def batch_caretaker_records(batch_id: str, limit: int = RequestQuery(100, ge=1, le=100),
                            offset: int = RequestQuery(0, ge=0), actor: dict = Depends(get_current_user)):
    profiles = db.list_documents(db_id, db_collection_id1,
        queries=[Query.equal('email', [actor.get('email', '')]), Query.limit(2)]).get('documents', [])
    if len(profiles) != 1:
        raise HTTPException(403, 'User profile is unavailable')
    try:
        batch = db.get_document(db_id, db_collection_id5, batch_id)
        farm = db.get_document(db_id, db_collection_id2, batch['farmID'])
    except Exception:
        raise HTTPException(404, 'Batch or farm not found')
    if not can_review_records(effective_profile(profiles[0], actor.get('_active_role')), farm):
        raise HTTPException(403, 'You cannot review records for this farm')
    result = db.list_documents(db_id, db_collection_id24, queries=[
        Query.equal('batch_id', [batch_id]), Query.equal('farm_id', [batch['farmID']]),
        Query.order_desc('record_date'), Query.order_desc('$id'),
        Query.limit(limit), Query.offset(offset)])
    return {'documents': result.get('documents', []), 'total': result.get('total', 0)}


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
    water_temperature: Annotated[str, Form()] = "",
    water_bought_litres: Annotated[str, Form()] = "",
    water_bought_amount: Annotated[str, Form()] = "",
    ac_water_litres: Annotated[str, Form()] = "",
    planted_count: Annotated[str, Form()] = "",
    transplanted_count: Annotated[str, Form()] = "",
    harvested_count: Annotated[str, Form()] = "",
    harvest_weight_kg: Annotated[str, Form()] = "",
    actor: dict = Depends(current_member),
):
    try:
        farm = db.get_document(db_id, db_collection_id2, farm_id)
    except Exception:
        raise HTTPException(404, 'Farm not found.') from None
    if actor.get('role') != 'caretaker' or not is_farm_caretaker(farm, actor):
        raise HTTPException(403, 'You are not an assigned caretaker for this farm.')
    created_by, created_by_name = actor['$id'], actor.get('name', '')
    if not farm_id.strip() or not farm_name.strip():
        raise HTTPException(status_code=400, detail="Farm is required")
    if has_issues and not issue_description.strip():
        raise HTTPException(status_code=400, detail="Issue description is required")

    try:
        water_values = water_record_values(record_type, water_bought_litres, water_bought_amount, ac_water_litres, water_temperature)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

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
    if has_batch_update or batch_id.strip():
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

        _ensure_batch_open(batch)
        try:
            plan = record_growth_plan(batch, lambda identity: db.get_document(db_id, db_collection_id3, identity))
            growth_stage = growth_stage_at(plan, batch.get('start_date'), record_date)
        except ValueError as error:
            raise HTTPException(422, 'Unable to determine the growth stage: ' + str(error)) from error
        except Exception as error:
            raise HTTPException(503, 'Unable to load the plant growth plan. Please retry.') from error

        if str(batch.get("farmID") or "").strip() != farm_id.strip():
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="The selected batch does not belong to this farm.",
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

    data.update(water_values)
    try:
        data.update(water_parameter_values(ph, ec))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    optional_numbers = {
        "temperature": _float_or_none(temperature),
        "humidity": _float_or_none(humidity),
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
        # Preserve the existing optional issue email; the shared event policy
        # below persists one notification for each relevant farm team member.
        if has_issues and batch is not None and batch_update and batch.get('farm_manager_id'):
            try:
                queue_notification_email(str(batch['farm_manager_id']), 'Batch issue reported',
                    f"{created_by_name} reported a {issue_severity.value} issue for {batch.get('batch_no', batch_number)}: {issue_description.strip()}"[:500], 'batch')
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Issue email could not be queued')
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
