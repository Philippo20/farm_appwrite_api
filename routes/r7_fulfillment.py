from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date, timezone
from pydantic import BaseModel, Field
from main import db_id, db_collection_id5, db_collection_id7
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
