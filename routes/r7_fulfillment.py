from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date, timezone
from pydantic import BaseModel, Field
from main import (
    db_id,
    db_collection_id1,
    db_collection_id5,
    db_collection_id7,
    db_collection_id9,
)
from db import db
from appwrite.id import ID
from audit_utils import write_audit
from routes.r25_notifications import create_notification

collection7_router = APIRouter(tags=["Fulfillment"])

class Status(str, Enum):
    ACTIVE = "Received"
    INACTIVE = "Packaging"
    PENDING= "Packaged"
    SENT_TO_SALES = "Sent to Sales"
    COMPLETED= "Completed"

class DeliveryStatus(str, Enum):
    PENDING_APPROVAL = "Pending Approval"
    PENDING_PICKUP = "Pending Pickup"
    SCHEDULED = "Scheduled"
    IN_TRANSIT = "In Transit"
    DELIVERED = "Delivered"
    ON_HOLD = "On Hold"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"

class DeliveryPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class HarvestInspectionPayload(BaseModel):
    total_heads: float = Field(ge=0)
    total_weight: float = Field(ge=0)
    packaging_supervisor_id: str = Field(default="Unassigned", max_length=225)
    packaging_type: str = Field(default="Pending assignment", max_length=225)
    temperature: str = Field(default="N/A", max_length=50)
    priority: DeliveryPriority = DeliveryPriority.MEDIUM
    notes: str = Field(default="", max_length=1000)
    inspected_by_id: str = Field(default="system", max_length=225)
    inspected_by_name: str = Field(default="Fulfillment Manager", max_length=225)
    inspection_confirmed: bool = False


class HarvestReleasePayload(BaseModel):
    released_by_id: str = Field(default="system", max_length=225)
    released_by_name: str = Field(default="Fulfillment Manager", max_length=225)


class PackagingRecordPayload(BaseModel):
    package_id: str = Field(min_length=1, max_length=225)
    package_count: int = Field(ge=1)
    waste_weight: float = Field(default=0, ge=0)
    waste_type: str = Field(default="None", max_length=225)
    notes: str = Field(default="", max_length=1000)
    complete: bool = False
    recorded_by_id: str = Field(min_length=1, max_length=225)
    recorded_by_name: str = Field(default="Packaging Supervisor", max_length=225)


def _batch_number(batch):
    return str(batch.get("batch_no") or batch.get("batch_id") or batch.get("$id") or "").strip()


def _find_fulfillment_for_batch(batch_number):
    normalized = batch_number.casefold()
    result = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id7,
    )
    return next(
        (
            item
            for item in result.get("documents", [])
            if str(item.get("batch_number") or "").strip().casefold() == normalized
        ),
        None,
    )


def _package_weight_kg(package):
    capacity = float(package.get("weight_capacity") or 0)
    unit = str(package.get("unit") or "kg").strip().casefold()
    if unit in {"g", "gram", "grams"}:
        return capacity / 1000
    if unit in {"mg", "milligram", "milligrams"}:
        return capacity / 1_000_000
    if unit in {"lb", "lbs", "pound", "pounds"}:
        return capacity * 0.45359237
    if unit in {"oz", "ounce", "ounces"}:
        return capacity * 0.028349523125
    return capacity


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalized(value):
    return str(value or "").strip().casefold()


@collection7_router.post("/fulfillments/intake/{batch_id}/inspect")
def inspect_harvest_intake(batch_id: str, payload: HarvestInspectionPayload):
    if not payload.inspection_confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confirm that the intake inspection has been completed.",
        )
    if payload.total_heads <= 0 and payload.total_weight <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter the received head count or received weight.",
        )

    try:
        batch = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id5,
            document_id=batch_id,
        )
        batch_status = str(batch.get("production_status") or "").strip().casefold()
        if batch_status not in {"harvested", "delivered"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only harvested batches can enter fulfillment intake.",
            )

        batch_number = _batch_number(batch)
        existing = _find_fulfillment_for_batch(batch_number)
        existing_status = str((existing or {}).get("status") or "").strip()
        if existing is not None and existing_status not in {"", Status.ACTIVE.value}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This batch has already advanced to {existing_status}.",
            )
        now = datetime.now(timezone.utc).isoformat()
        inspection_data = {
            "batch_number": batch_number,
            "farm_manager_id": str(batch.get("farm_manager_id") or "Unassigned"),
            "farm_name": str(batch.get("farm_name") or "Unassigned Farm"),
            "plant_type": str(batch.get("plant_name") or "Unspecified crop"),
            "total_heads": payload.total_heads,
            "total_weight": payload.total_weight,
            "harvest_received_images": str(batch.get("harvest_images") or "")[:225],
            "packaging_supervisor_id": payload.packaging_supervisor_id.strip() or "Unassigned",
            "packaging_type": payload.packaging_type.strip() or "Pending assignment",
            "packaging_weight": 0.0,
            "total_packaged_weight": 0.0,
            "packaging_waste_type": "None",
            "packaging_waste_weight": 0.0,
            "packaging_images": "",
            "yield_loss_percentage": 0.0,
            "received_date_time": now,
            "packaging_date_time": now,
            "sent_to_sales": False,
            "sent_to_sales_date_time": now,
            "status": Status.ACTIVE.value,
            "delivery_status": DeliveryStatus.DELIVERED.value,
            "driver_name": "Unassigned",
            "vehicle": "Pending",
            "destination": "Farm Estates Hub",
            "address": "",
            "eta": "Received",
            "temperature": payload.temperature.strip() or "N/A",
            "priority": payload.priority.value,
            "delivery_note": payload.notes.strip(),
        }

        if existing is None:
            inspection_data["fulfillment_id"] = ID.unique()
            saved = db.create_document(
                database_id=db_id,
                collection_id=db_collection_id7,
                document_id=ID.unique(),
                data=inspection_data,
            )
            action = "Create"
        else:
            saved = db.update_document(
                database_id=db_id,
                collection_id=db_collection_id7,
                document_id=existing["$id"],
                data=inspection_data,
            )
            action = "Update"

        write_audit(
            action_type=action,
            collection_name="Fulfillment",
            performed_by_id=payload.inspected_by_id,
            performed_by_role="fulfillment_manager",
            action_details=f"Inspected harvest intake for batch {batch_number}",
            previous_data=existing,
            new_data=inspection_data,
        )
        return {
            "message": "Harvest intake inspection saved",
            "fulfillment": saved,
            "batch": batch,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not inspect harvest intake: {error}") from error


@collection7_router.post("/fulfillments/intake/{batch_id}/release")
def release_harvest_to_packaging(batch_id: str, payload: HarvestReleasePayload):
    try:
        batch = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id5,
            document_id=batch_id,
        )
        batch_number = _batch_number(batch)
        fulfillment = _find_fulfillment_for_batch(batch_number)
        if fulfillment is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inspect this harvest before releasing it to packaging.",
            )

        current_status = str(fulfillment.get("status") or "").strip()
        if current_status == Status.INACTIVE.value:
            if str(batch.get("production_status") or "").strip() != "Delivered":
                batch = db.update_document(
                    database_id=db_id,
                    collection_id=db_collection_id5,
                    document_id=batch_id,
                    data={
                        "production_status": "Delivered",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            return {
                "message": "Batch is already in packaging",
                "fulfillment": fulfillment,
                "batch": batch,
            }
        if current_status != Status.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A fulfillment in {current_status or 'unknown'} status cannot be released from intake.",
            )

        now = datetime.now(timezone.utc).isoformat()
        fulfillment_update = {
            "status": Status.INACTIVE.value,
            "packaging_date_time": now,
            "eta": "Released to packaging",
        }
        updated_fulfillment = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id7,
            document_id=fulfillment["$id"],
            data=fulfillment_update,
        )

        batch_update = {
            "production_status": "Delivered",
            "updated_at": now,
        }
        try:
            updated_batch = db.update_document(
                database_id=db_id,
                collection_id=db_collection_id5,
                document_id=batch_id,
                data=batch_update,
            )
        except Exception:
            db.update_document(
                database_id=db_id,
                collection_id=db_collection_id7,
                document_id=fulfillment["$id"],
                data={"status": Status.ACTIVE.value},
            )
            raise

        write_audit(
            action_type="Update",
            collection_name="Fulfillment",
            performed_by_id=payload.released_by_id,
            performed_by_role="fulfillment_manager",
            action_details=f"Released batch {batch_number} to packaging",
            previous_data=fulfillment,
            new_data=fulfillment_update,
        )
        write_audit(
            action_type="Update",
            collection_name="Batches",
            performed_by_id=payload.released_by_id,
            performed_by_role="fulfillment_manager",
            action_details=f"Marked batch {batch_number} delivered to the hub",
            previous_data=batch,
            new_data=batch_update,
        )

        supervisor_id = str(fulfillment.get("packaging_supervisor_id") or "").strip()
        if supervisor_id and supervisor_id.casefold() not in {"unassigned", "system"}:
            try:
                create_notification(
                    recipient_id=supervisor_id,
                    recipient_name="Packaging Supervisor",
                    title="Harvest released to packaging",
                    message=f"Batch {batch_number} from {batch.get('farm_name') or 'a farm'} is ready for packaging.",
                    notification_type="batch",
                    priority="high" if fulfillment.get("priority") == "High" else "normal",
                )
            except Exception as notification_error:
                print(f"Packaging release notification failed: {notification_error}")

        return {
            "message": "Harvest released to packaging",
            "fulfillment": updated_fulfillment,
            "batch": updated_batch,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not release harvest: {error}") from error


@collection7_router.post("/fulfillments/{fulfillment_id}/packaging-record")
def record_packaging_output(fulfillment_id: str, payload: PackagingRecordPayload):
    """Record one packaging run and keep material stock and fulfillment totals in sync."""
    package_before = None
    try:
        fulfillment = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id7,
            document_id=fulfillment_id,
        )
        current_status = str(fulfillment.get("status") or "").strip()
        if current_status != Status.INACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only batches released to Packaging can be recorded."
                    if current_status != Status.PENDING.value
                    else "This batch has already completed packaging."
                ),
            )

        package_before = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id9,
            document_id=payload.package_id,
        )
        if _normalized(package_before.get("status")) != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The selected packaging material is not active.",
            )

        package_name = str(package_before.get("package_name") or "").strip()
        package_crop = _normalized(package_before.get("plant_type_name"))
        fulfillment_crop = _normalized(fulfillment.get("plant_type"))
        if package_crop and fulfillment_crop and package_crop != fulfillment_crop:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{package_name or 'This package'} is configured for {package_before.get('plant_type_name')}, not {fulfillment.get('plant_type')}.",
            )

        previous_type = str(fulfillment.get("packaging_type") or "").strip()
        if (
            _number(fulfillment.get("total_packaged_weight")) > 0
            and previous_type
            and _normalized(previous_type) not in {"pending assignment", _normalized(package_name)}
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This batch is already being recorded with {previous_type}.",
            )

        available = _number(package_before.get("quantity_available"))
        if available < payload.package_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only {available:g} package units are available.",
            )

        unit_weight_kg = _package_weight_kg(package_before)
        if unit_weight_kg <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The selected package needs a valid weight capacity.",
            )

        previous_output = _number(fulfillment.get("total_packaged_weight"))
        previous_waste = _number(fulfillment.get("packaging_waste_weight"))
        received_weight = _number(fulfillment.get("total_weight"))
        entry_output = unit_weight_kg * payload.package_count
        new_output = previous_output + entry_output
        new_waste = previous_waste + payload.waste_weight
        tolerance = max(0.05, received_weight * 0.02)
        if received_weight > 0 and new_output + new_waste > received_weight + tolerance:
            remaining = max(0.0, received_weight - previous_output - previous_waste)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"This entry exceeds the remaining received weight of {remaining:.2f} kg.",
            )
        if (
            payload.complete
            and received_weight > 0
            and received_weight - new_output - new_waste > tolerance
        ):
            unaccounted = received_weight - new_output - new_waste
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Account for the remaining {unaccounted:.2f} kg as packaged output or waste before completing this batch.",
            )

        now = datetime.now(timezone.utc).isoformat()
        existing_notes = str(fulfillment.get("delivery_note") or "").strip()
        entry_notes = payload.notes.strip()
        combined_notes = existing_notes
        if entry_notes:
            note_line = f"Packaging: {entry_notes}"
            combined_notes = f"{existing_notes}\n{note_line}".strip()[-1000:]

        fulfillment_update = {
            "packaging_supervisor_id": payload.recorded_by_id,
            "packaging_type": package_name or "Packaging material",
            "packaging_weight": round(unit_weight_kg, 6),
            "total_packaged_weight": round(new_output, 6),
            "packaging_waste_type": (
                payload.waste_type.strip() or "Other"
                if payload.waste_weight > 0
                else str(fulfillment.get("packaging_waste_type") or "None")
            ),
            "packaging_waste_weight": round(new_waste, 6),
            "yield_loss_percentage": (
                round(new_waste / received_weight * 100, 2) if received_weight > 0 else 0.0
            ),
            "packaging_date_time": now,
            "status": Status.PENDING.value if payload.complete else Status.INACTIVE.value,
            "eta": "Packaging completed" if payload.complete else "Packaging in progress",
            "delivery_note": combined_notes,
        }
        package_update = {
            "quantity_available": available - payload.package_count,
            "updated_at": now,
            "status": (
                "Out_of_stock"
                if available - payload.package_count <= 0
                else str(package_before.get("status") or "Active")
            ),
        }

        db.update_document(
            database_id=db_id,
            collection_id=db_collection_id9,
            document_id=payload.package_id,
            data=package_update,
        )
        try:
            saved = db.update_document(
                database_id=db_id,
                collection_id=db_collection_id7,
                document_id=fulfillment_id,
                data=fulfillment_update,
            )
        except Exception:
            db.update_document(
                database_id=db_id,
                collection_id=db_collection_id9,
                document_id=payload.package_id,
                data={
                    "quantity_available": available,
                    "updated_at": str(package_before.get("updated_at") or now),
                    "status": str(package_before.get("status") or "Active"),
                },
            )
            raise

        write_audit(
            action_type="Update",
            collection_name="Fulfillment",
            performed_by_id=payload.recorded_by_id,
            performed_by_role="packaging_supervisor",
            action_details=(
                f"Recorded {payload.package_count} {package_name or 'package'} units "
                f"for batch {fulfillment.get('batch_number')}"
            ),
            previous_data=fulfillment,
            new_data=fulfillment_update,
        )
        write_audit(
            action_type="Update",
            collection_name="Package",
            performed_by_id=payload.recorded_by_id,
            performed_by_role="packaging_supervisor",
            action_details=f"Used {payload.package_count} units of {package_name}",
            previous_data=package_before,
            new_data=package_update,
        )

        if payload.complete:
            try:
                users = db.list_documents(
                    database_id=db_id,
                    collection_id=db_collection_id1,
                ).get("documents", [])
                for user in users:
                    if _normalized(user.get("role")) != "quality_officer":
                        continue
                    recipient_id = str(user.get("$id") or user.get("user_id") or "").strip()
                    if not recipient_id:
                        continue
                    create_notification(
                        recipient_id=recipient_id,
                        recipient_name=str(user.get("name") or "Quality Assurance"),
                        title="Batch ready for quality inspection",
                        message=f"Batch {fulfillment.get('batch_number')} has completed packaging.",
                        notification_type="batch",
                        priority="high",
                    )
            except Exception as notification_error:
                print(f"Packaging completion notification failed: {notification_error}")

        return {
            "message": "Packaging completed" if payload.complete else "Packaging output recorded",
            "fulfillment": saved,
            "entry": {
                "package_name": package_name,
                "package_count": payload.package_count,
                "unit_weight_kg": unit_weight_kg,
                "output_weight_kg": entry_output,
                "waste_weight_kg": payload.waste_weight,
            },
            "package_stock_remaining": available - payload.package_count,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not record packaging output: {error}") from error

@collection7_router.post("/fulfillment/info")
def register_fulfillment(
        batch_number: Annotated[str, Form()],
        farm_manager_id: Annotated[str, Form()],
        farm_name: Annotated[str, Form()],
        plant_type: Annotated[str, Form()],
        total_heads: Annotated[float, Form(...)],
        total_weight: Annotated[float, Form()],
        harvest_received_images: Annotated[str, Form()],
        packaging_supervisor_id: Annotated[str, Form()],
        packaging_type: Annotated[str, Form()],
        packaging_weight: Annotated[float, Form()],
        total_packaged_weight: Annotated[float, Form()],
        packaging_waste_type: Annotated[str, Form()],
        packaging_waste_weight: Annotated[float, Form()],
        packaging_images: Annotated[str, Form()],
        yield_loss_percentage: Annotated[float, Form()],
        received_date_time: Annotated[date, Form(...)],
        packaging_date_time: Annotated[date, Form(...)],
        sent_to_sales: Annotated[bool, Form()],
        sent_to_sales_date_time: Annotated[date, Form(...)],
        status: Annotated[Status, Form()],
        delivery_status: Annotated[DeliveryStatus, Form()] = DeliveryStatus.PENDING_APPROVAL,
        driver_name: Annotated[str, Form()] = "Unassigned",
        vehicle: Annotated[str, Form()] = "Pending",
        destination: Annotated[str, Form()] = "Sales Hub",
        address: Annotated[str, Form()] = "",
        scheduled_date: Annotated[date | None, Form()] = None,
        eta: Annotated[str, Form()] = "",
        temperature: Annotated[str, Form()] = "N/A",
        priority: Annotated[DeliveryPriority, Form()] = DeliveryPriority.MEDIUM,
        delivery_note: Annotated[str, Form()] = ""
        ):
    audits_info = {
        "fulfillment_id": ID.unique(),
        "batch_number": batch_number,
        "farm_manager_id": farm_manager_id,
        "farm_name": farm_name,
        "plant_type": plant_type,
        "total_heads": total_heads,
        "total_weight": total_weight,
        "harvest_received_images": harvest_received_images,
        "packaging_supervisor_id": packaging_supervisor_id,
        "packaging_type": packaging_type,
        "packaging_weight": packaging_weight,
        "total_packaged_weight": total_packaged_weight,
        "packaging_waste_type": packaging_waste_type,
        "packaging_waste_weight": packaging_waste_weight,
        "packaging_images": packaging_images,
        "yield_loss_percentage": yield_loss_percentage,
        "received_date_time": received_date_time.isoformat(),
        "packaging_date_time": packaging_date_time.isoformat(),
        "sent_to_sales": sent_to_sales,
        "sent_to_sales_date_time": sent_to_sales_date_time.isoformat(),
        "status": status,
        "delivery_status": delivery_status,
        "driver_name": driver_name,
        "vehicle": vehicle,
        "destination": destination,
        "address": address,
        "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
        "eta": eta,
        "temperature": temperature,
        "priority": priority,
        "delivery_note": delivery_note
    }
    if audits_info["scheduled_date"] is None:
        audits_info.pop("scheduled_date")
    print(audits_info)

    fulfillment_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id7,
        document_id=ID.unique(),
        data= audits_info
    )
    write_audit(
        action_type="Create",
        collection_name="Fulfillment",
        performed_by_id=farm_manager_id,
        performed_by_role="farm_manager",
        action_details=f"Created fulfillment delivery record for batch {batch_number}",
        new_data=audits_info
    )

    return {
        "message": "User registered successfully",
        "fulfillment_id": fulfillment_create["$id"]
    }

@collection7_router.get("/fulfillments")
def get_all_fulfillment_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id7
        )

        # Extract the list of users
        audit_users = result["documents"]

        return {
            "count": len(audit_users),
            "users": audit_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection7_router.get("/fulfillment/{fulfillment_id}")
def get_fulfillment_info(fulfillment_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id7,
            document_id= fulfillment_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection7_router.put("/fulfillments/{fulfillment_id}")
def update_fulfillment(fulfillment_id:str,
    batch_number: Annotated[str, Form()],
    farm_manager_id: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    plant_type: Annotated[str, Form()],
    total_heads: Annotated[float, Form(...)],
    total_weight: Annotated[float, Form()],
    harvest_received_images: Annotated[str, Form()],
    packaging_supervisor_id: Annotated[str, Form()],
    packaging_type: Annotated[str, Form()],
    packaging_weight: Annotated[float, Form()],
    total_packaged_weight: Annotated[float, Form()],
    packaging_waste_type: Annotated[str, Form()],
    packaging_waste_weight: Annotated[float, Form()],
    packaging_images: Annotated[str, Form()],
    yield_loss_percentage: Annotated[float, Form()],
    received_date_time: Annotated[date, Form(...)],
    packaging_date_time: Annotated[date, Form(...)],
    sent_to_sales: Annotated[bool, Form()],
    sent_to_sales_date_time: Annotated[date, Form(...)],
    status: Annotated[Status, Form()],
    delivery_status: Annotated[DeliveryStatus, Form()] = DeliveryStatus.PENDING_APPROVAL,
    driver_name: Annotated[str, Form()] = "Unassigned",
    vehicle: Annotated[str, Form()] = "Pending",
    destination: Annotated[str, Form()] = "Sales Hub",
    address: Annotated[str, Form()] = "",
    scheduled_date: Annotated[date | None, Form()] = None,
    eta: Annotated[str, Form()] = "",
    temperature: Annotated[str, Form()] = "N/A",
    priority: Annotated[DeliveryPriority, Form()] = DeliveryPriority.MEDIUM,
    delivery_note: Annotated[str, Form()] = ""
    ):
    try:
        previous_fulfillment = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id7,
            document_id=fulfillment_id
        )
        update_data = {"batch_number": batch_number,
                  "farm_manager_id": farm_manager_id,
                  "farm_name": farm_name,
                  "plant_type": plant_type,
                  "total_heads": total_heads,
                  "total_weight": total_weight,
                  "harvest_received_images": harvest_received_images,
                  "packaging_supervisor_id": packaging_supervisor_id,
                  "packaging_type": packaging_type,
                  "packaging_weight": packaging_weight,
                  "total_packaged_weight": total_packaged_weight,
                  "packaging_waste_type": packaging_waste_type,
                  "packaging_waste_weight": packaging_waste_weight,
                  "packaging_images": packaging_images,
                  "yield_loss_percentage": yield_loss_percentage,
                  "received_date_time": received_date_time.isoformat(),
                  "packaging_date_time": packaging_date_time.isoformat(),
                  "sent_to_sales": sent_to_sales,
                  "sent_to_sales_date_time": sent_to_sales_date_time.isoformat(),
                  "status": status,
                  "delivery_status": delivery_status,
                  "driver_name": driver_name,
                  "vehicle": vehicle,
                  "destination": destination,
                  "address": address,
                  "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
                  "eta": eta,
                  "temperature": temperature,
                  "priority": priority,
                  "delivery_note": delivery_note
            }
        if update_data["scheduled_date"] is None:
            update_data.pop("scheduled_date")
        # Perform update
        updated_farm_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id7,
            document_id=fulfillment_id,
            data=update_data,
            permissions=[]
        )
        write_audit(
            action_type="Update",
            collection_name="Fulfillment",
            performed_by_id=packaging_supervisor_id or farm_manager_id,
            performed_by_role="fulfillment_manager",
            action_details=f"Updated fulfillment delivery record for batch {batch_number}",
            previous_data=previous_fulfillment,
            new_data=update_data
        )
        return {"message": "Fulfillments info updated successfully", "user": updated_farm_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection7_router.delete("/fulfillments/{fulfillment_id}")
def delete_fulfillment(fulfillment_id:str):
    try:
        previous_fulfillment = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id7,
            document_id=fulfillment_id
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id7, 
            document_id=fulfillment_id)
        write_audit(
            action_type="Delete",
            collection_name="Fulfillment",
            performed_by_id=previous_fulfillment.get("farm_manager_id", "system"),
            performed_by_role="fulfillment_manager",
            action_details=f"Deleted fulfillment delivery record {previous_fulfillment.get('batch_number', fulfillment_id)}",
            previous_data=previous_fulfillment
        )
        return {"message": f"Delivery with ID {fulfillment_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
