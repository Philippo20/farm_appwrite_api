from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id7, db_collection_id8
from db import db
from appwrite.id import ID
from audit_utils import write_audit

collection8_router = APIRouter(tags=["Sales"])

class Status(str, Enum):
    PENDING = "Pending"
    DELIVERED = "Delivered"
    CANCELLED= "Cancelled"

class OfftakerStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


def _normalized(value):
    return str(value or "").strip().casefold()


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _integer(value):
    return max(0, int(round(_number(value))))


def _batch_number(fulfillment):
    return str(fulfillment.get("batch_number") or "").strip()


def _find_fulfillment(reference):
    wanted = _normalized(reference)
    if not wanted:
        return None
    documents = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id7,
    ).get("documents", [])
    return next(
        (
            item
            for item in documents
            if wanted
            in {
                _normalized(item.get("$id")),
                _normalized(item.get("fulfillment_id")),
                _normalized(item.get("batch_number")),
            }
        ),
        None,
    )


def _fulfillment_pack_count(fulfillment):
    recorded = _integer(fulfillment.get("total_package_count"))
    if recorded > 0:
        return recorded
    total_weight = _number(fulfillment.get("total_packaged_weight"))
    unit_weight = _number(fulfillment.get("packaging_weight"))
    return _integer(total_weight / unit_weight) if unit_weight > 0 else 0


def _allocated_pack_count(
    batch_number,
    *,
    exclude_sale_id="",
    fallback_unit_weight=0.0,
):
    wanted = _normalized(batch_number)
    total = 0
    documents = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id8,
    ).get("documents", [])
    for sale in documents:
        if str(sale.get("$id") or "") == exclude_sale_id:
            continue
        if _normalized(sale.get("status")) == "cancelled":
            continue
        sale_batch = sale.get("batch_number") or sale.get("batch_id")
        if _normalized(sale_batch) != wanted:
            continue
        package_count = _integer(sale.get("package_count"))
        if package_count <= 0:
            unit_weight = _number(sale.get("unit_weight_kg")) or fallback_unit_weight
            if unit_weight > 0:
                package_count = _integer(
                    _number(sale.get("quantity_delivered")) / unit_weight
                )
        total += package_count
    return total


def _validated_allocation(batch_reference, package_count, *, exclude_sale_id=""):
    fulfillment = _find_fulfillment(batch_reference)
    if fulfillment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The selected QA-approved batch could not be found.",
        )
    if _normalized(fulfillment.get("status")) != "sent to sales" or _normalized(
        fulfillment.get("quality_status")
    ) != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only QA-approved batches released to sales can be allocated.",
        )
    requested = _integer(package_count)
    if requested <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter at least one pack for this delivery.",
        )
    total_packs = _fulfillment_pack_count(fulfillment)
    allocated = _allocated_pack_count(
        _batch_number(fulfillment),
        exclude_sale_id=exclude_sale_id,
        fallback_unit_weight=_number(fulfillment.get("packaging_weight")),
    )
    available = max(0, total_packs - allocated)
    if requested > available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {available} packs remain available for this batch.",
        )
    return fulfillment, available

@collection8_router.post("/sales/info")
def register_sales(
        batch_id: Annotated[str, Form()],
        buyer_id: Annotated[str, Form()],
        buyer_name: Annotated[str, Form()],
        delivered_by: Annotated[str, Form(...)],
        delivered_at: Annotated[datetime, Form()],
        quantity_delivered: Annotated[float, Form()],
        total_amount: Annotated[float, Form()],
        paid: Annotated[bool, Form()],
        payment_mode: Annotated[str, Form()],
        receipt_image: Annotated[str, Form()],
        receipt_number: Annotated[str, Form()],
        payment_date: Annotated[date, Form()],
        created_by: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        off_taker_id: Annotated[str, Form()] = "",
        batch_number: Annotated[str, Form()] = "",
        fulfillment_id: Annotated[str, Form()] = "",
        package_count: Annotated[int, Form()] = 0,
        delivery_address: Annotated[str, Form()] = "",
        delivery_notes: Annotated[str, Form()] = "",
        created_by_role: Annotated[str, Form()] = "sales_manager",
        scheduled_for: Annotated[datetime | None, Form()] = None
        ):
    fulfillment, _ = _validated_allocation(
        fulfillment_id or batch_number or batch_id,
        package_count,
    )
    canonical_batch = _batch_number(fulfillment)
    unit_weight = _number(fulfillment.get("packaging_weight"))
    allocated_weight = round(unit_weight * package_count, 6)
    scheduled_value = scheduled_for or delivered_at
    sales_info = {
        "batch_id": canonical_batch,
        "batch_number": canonical_batch,
        "fulfillment_id": str(fulfillment.get("$id") or fulfillment_id),
        "crop_variety": str(
            fulfillment.get("plant_variety") or fulfillment.get("plant_type") or ""
        ).strip(),
        "package_type": str(fulfillment.get("packaging_type") or "").strip(),
        "package_count": package_count,
        "unit_weight_kg": unit_weight,
        "buyer_id": buyer_id,
        "off_taker_id": off_taker_id,
        "buyer_name": buyer_name,
        "delivered_by": delivered_by,
        "delivered_at": delivered_at.isoformat(),
        "scheduled_for": scheduled_value.isoformat(),
        "quantity_delivered": allocated_weight,
        "total_amount": total_amount,
        "paid": paid,
        "payment_mode": payment_mode,
        "receipt_image": receipt_image,
        "receipt_number": receipt_number,
        "payment_date": payment_date.isoformat(),
        "created_by": created_by,
        "status": status,
        "delivery_address": delivery_address.strip(),
        "delivery_notes": delivery_notes.strip(),
    }
    if status == Status.DELIVERED:
        sales_info["completed_at"] = datetime.now().isoformat()
    print(sales_info)

    sales_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id8,
        document_id=ID.unique(),
        data= sales_info
    )
    write_audit(
        action_type="Create",
        collection_name="Sales",
        performed_by_id=created_by,
        performed_by_role=created_by_role.strip() or "sales_manager",
        action_details=(
            f"Allocated {package_count} packs ({allocated_weight:.2f} kg) "
            f"from batch {canonical_batch} to {buyer_name}"
        ),
        new_data=sales_info
    )

    return {
        "message": "User registered successfully",
        "sales_id": sales_create["$id"],
        "sale": sales_create
    }

@collection8_router.get("/sales")
def get_all_sales_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id8
        )

        sales_users = result["documents"]

        for sale in sales_users:
            fulfillment = _find_fulfillment(
                sale.get("fulfillment_id")
                or sale.get("batch_number")
                or sale.get("batch_id")
            )
            if fulfillment is None:
                continue
            batch_number = _batch_number(fulfillment)
            total_packs = _fulfillment_pack_count(fulfillment)
            unit_weight = _number(fulfillment.get("packaging_weight"))
            package_count = _integer(sale.get("package_count"))
            if package_count <= 0 and unit_weight > 0:
                package_count = _integer(
                    _number(sale.get("quantity_delivered")) / unit_weight
                )
            legacy_update = {}
            if package_count > 0 and _integer(sale.get("package_count")) <= 0:
                legacy_update["package_count"] = package_count
            if _number(sale.get("unit_weight_kg")) <= 0 and unit_weight > 0:
                legacy_update["unit_weight_kg"] = unit_weight
            if not str(sale.get("fulfillment_id") or "").strip():
                legacy_update["fulfillment_id"] = str(fulfillment.get("$id") or "")
            if not str(sale.get("crop_variety") or "").strip():
                legacy_update["crop_variety"] = str(
                    fulfillment.get("plant_variety")
                    or fulfillment.get("plant_type")
                    or ""
                ).strip()
            if not str(sale.get("package_type") or "").strip():
                legacy_update["package_type"] = str(
                    fulfillment.get("packaging_type") or ""
                ).strip()
            if not str(sale.get("scheduled_for") or "").strip() and sale.get(
                "delivered_at"
            ):
                legacy_update["scheduled_for"] = sale["delivered_at"]
            if legacy_update:
                try:
                    db.update_document(
                        database_id=db_id,
                        collection_id=db_collection_id8,
                        document_id=sale["$id"],
                        data=legacy_update,
                    )
                except Exception:
                    pass
                sale.update(legacy_update)
            sale["batch_number"] = batch_number
            sale["total_batch_packs"] = total_packs
            sale["available_package_count"] = max(
                0,
                total_packs
                - _allocated_pack_count(
                    batch_number,
                    fallback_unit_weight=unit_weight,
                ),
            )

        return {
            "count": len(sales_users),
            "users": sales_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection8_router.get("/sale/{sale_id}")
def get_sale_info(sale_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id8,
            document_id= sale_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found!")
    
@collection8_router.put("/sales/{sale_id}")
def update_sale(sale_id:str,
    batch_id: Annotated[str, Form()],
    buyer_id: Annotated[str, Form()],
    buyer_name: Annotated[str, Form()],
    delivered_by: Annotated[str, Form(...)],
    delivered_at: Annotated[datetime, Form()],
    quantity_delivered: Annotated[float, Form()],
    total_amount: Annotated[float, Form()],
    paid: Annotated[bool, Form()],
    payment_mode: Annotated[str, Form()],
    receipt_image: Annotated[str, Form()],
    receipt_number: Annotated[str, Form()],
    payment_date: Annotated[date, Form()],
    created_by: Annotated[str, Form()],
    status: Annotated[Status, Form()],
    off_taker_id: Annotated[str, Form()] = "",
    batch_number: Annotated[str, Form()] = "",
    fulfillment_id: Annotated[str, Form()] = "",
    package_count: Annotated[int, Form()] = 0,
    delivery_address: Annotated[str, Form()] = "",
    delivery_notes: Annotated[str, Form()] = "",
    created_by_role: Annotated[str, Form()] = "sales_manager",
    scheduled_for: Annotated[datetime | None, Form()] = None
    ):
    try:
        previous_sale = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id8,
            document_id=sale_id
        )
        fulfillment, _ = _validated_allocation(
            fulfillment_id or batch_number or batch_id,
            package_count,
            exclude_sale_id=sale_id,
        )
        canonical_batch = _batch_number(fulfillment)
        unit_weight = _number(fulfillment.get("packaging_weight"))
        allocated_weight = round(unit_weight * package_count, 6)
        scheduled_value = scheduled_for or delivered_at
        update_data = {"batch_id": canonical_batch,
                  "batch_number": canonical_batch,
                  "fulfillment_id": str(fulfillment.get("$id") or fulfillment_id),
                  "crop_variety": str(
                      fulfillment.get("plant_variety") or fulfillment.get("plant_type") or ""
                  ).strip(),
                  "package_type": str(fulfillment.get("packaging_type") or "").strip(),
                  "package_count": package_count,
                  "unit_weight_kg": unit_weight,
                  "buyer_id": buyer_id,
                  "off_taker_id": off_taker_id,
                  "buyer_name": buyer_name,
                  "delivered_by": delivered_by,
                  "delivered_at": delivered_at.isoformat(),
                  "scheduled_for": scheduled_value.isoformat(),
                  "quantity_delivered": allocated_weight,
                  "total_amount": total_amount,
                  "paid": paid,
                  "payment_mode": payment_mode,
                  "receipt_image": receipt_image,
                  "receipt_number": receipt_number,
                  "payment_date": payment_date.isoformat(),
                  "created_by": created_by,
                  "status": status,
                  "delivery_address": delivery_address.strip(),
                  "delivery_notes": delivery_notes.strip(),
            }
        if status == Status.DELIVERED:
            update_data["completed_at"] = str(
                previous_sale.get("completed_at") or datetime.now().isoformat()
            )
        # Perform update
        updated_sales_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id8,
            document_id=sale_id,
            data=update_data,
            permissions=[]
        )
        write_audit(
            action_type="Update",
            collection_name="Sales",
            performed_by_id=created_by,
            performed_by_role=created_by_role.strip() or "sales_manager",
            action_details=(
                f"Updated delivery allocation for batch {canonical_batch}: "
                f"{package_count} packs ({allocated_weight:.2f} kg)"
            ),
            previous_data=previous_sale,
            new_data=update_data
        )
        return {"message": "Sales info updated successfully", "user": updated_sales_info}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection8_router.delete("/sales/{sale_id}")
def delete_sale(sale_id:str):
    try:
        previous_sale = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id8,
            document_id=sale_id
        )
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id8, 
            document_id=sale_id)
        write_audit(
            action_type="Delete",
            collection_name="Sales",
            performed_by_id=previous_sale.get("created_by", "system"),
            performed_by_role="sales_person",
            action_details=f"Deleted sales delivery record {previous_sale.get('batch_id', sale_id)}",
            previous_data=previous_sale
        )
        return {"message": f"User with ID {sale_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
