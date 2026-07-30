from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id7
from db import db
from appwrite.id import ID
from audit_utils import write_audit

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
