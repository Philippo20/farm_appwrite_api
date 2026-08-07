from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date
from main import db_id, db_collection_id8
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
        off_taker_id: Annotated[str, Form()] = ""
        ):
    sales_info = {
        "batch_id": batch_id,
        "buyer_id": buyer_id,
        "off_taker_id": off_taker_id,
        "buyer_name": buyer_name,
        "delivered_by": delivered_by,
        "delivered_at": delivered_at.isoformat(),
        "quantity_delivered": quantity_delivered,
        "total_amount": total_amount,
        "paid": paid,
        "payment_mode": payment_mode,
        "receipt_image": receipt_image,
        "receipt_number": receipt_number,
        "payment_date": payment_date.isoformat(),
        "created_by": created_by,
        "status": status
    }
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
        performed_by_role="sales_person",
        action_details=f"Created sales delivery record for batch {batch_id}",
        new_data=sales_info
    )

    return {
        "message": "User registered successfully",
        "sales_id": sales_create["$id"]
    }

@collection8_router.get("/sales")
def get_all_sales_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id8
        )

        # Extract the list of users
        sales_users = result["documents"]

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
    off_taker_id: Annotated[str, Form()] = ""
    ):
    try:
        previous_sale = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id8,
            document_id=sale_id
        )
        update_data = {"batch_id": batch_id,
                  "buyer_id": buyer_id,
                  "off_taker_id": off_taker_id,
                  "buyer_name": buyer_name,
                  "delivered_by": delivered_by,
                  "delivered_at": delivered_at.isoformat(),
                  "quantity_delivered": quantity_delivered,
                  "total_amount": total_amount,
                  "paid": paid,
                  "payment_mode": payment_mode,
                  "receipt_image": receipt_image,
                  "receipt_number": receipt_number,
                  "payment_date": payment_date.isoformat(),
                  "created_by": created_by,
                  "status": status
            }
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
            performed_by_role="sales_person",
            action_details=f"Updated sales delivery record for batch {batch_id}",
            previous_data=previous_sale,
            new_data=update_data
        )
        return {"message": "Sales info updated successfully", "user": updated_sales_info}

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
