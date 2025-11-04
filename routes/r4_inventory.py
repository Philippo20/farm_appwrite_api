from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import date
from main import db_id, db_collection_id4
from db import db
from appwrite.id import ID
from appwrite.query import Query

collection4_router = APIRouter(tags=["Inventory"])

class Status(str, Enum):
    AVAILABLE = "Available"
    LOW_STOCK = "Low Stock"
    OUT_OF_STOCK = "Out of Stock"
    EXPIRED= "Expired"

@collection4_router.post("/inventory/info")
def register_inventory(
        item_name: Annotated[str, Form()],
        item_type: Annotated[str, Form()],
        unit: Annotated[str, Form()],
        quantity_available: Annotated[float, Form()],
        reorder_level: Annotated[float, Form()],
        unit_price: Annotated[float, Form()],
        total_value: Annotated[float, Form()],
        supplier_name: Annotated[str, Form()],
        batch_number: Annotated[str, Form()],
        farm_id: Annotated[str, Form()],
        added_by: Annotated[str, Form()],
        status: Annotated[Status, Form()],
        notes: Annotated[str, Form()],
        date_added: Annotated[date, Form(...)]
        ):
    
    # Ensure plant type info with name and caretakerID combined does not exist
    existing = db.list_documents(
        database_id=db_id,
        collection_id=db_collection_id4,
        queries=[
            Query.equal("item_name", [item_name])
        ]
    )
    if existing["total"] > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Plant type with name: {item_name} already exist!")
    

    inventory_info = {
        "item_id": ID.unique(),
        "item_name": item_name,
        "item_type": item_type,
        "unit": unit,
        "quantity_available": quantity_available,
        "reorder_level": reorder_level,
        "unit_price": unit_price,
        "total_value": total_value,
        "supplier_name": supplier_name,
        "batch_number": batch_number,
        "farm_id": farm_id,
        "notes": notes,
        "status": status,
        "added_by": added_by,        
        "date_added": date_added.isoformat()
    }
    print(inventory_info)

    inventory_create = db.create_document(
        database_id= db_id,
        collection_id=db_collection_id4,
        document_id=ID.unique(),
        data= inventory_info
    )

    return {
        "message": "Inventory registered successfully",
        "item_id": inventory_create["$id"]
    }

@collection4_router.get("/inventory")
def get_all_inventory_infos():
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id4
        )

        # Extract the list of users
        inventory_users = result["documents"]

        return {
            "count": len(inventory_users),
            "users": inventory_users
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@collection4_router.get("/inventory/{item_id}")
def get_inventory_info(item_id:str):
    try:
        user= db.get_document(
            database_id=db_id,
            collection_id= db_collection_id4,
            document_id= item_id
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e))
    
@collection4_router.put("/inventory/{item_id}")
def update_inventory(item_id:str,
    item_name: Annotated[str, Form()],
    item_type: Annotated[str, Form()],
    unit: Annotated[str, Form()],
    quantity_available: Annotated[float, Form()],
    reorder_level: Annotated[float, Form()],
    unit_price: Annotated[float, Form()],
    total_value: Annotated[float, Form()],
    supplier_name: Annotated[str, Form()],
    batch_number: Annotated[str, Form()],
    farm_id: Annotated[str, Form()],
    added_by: Annotated[str, Form()],
    status: Annotated[Status, Form()],
    notes: Annotated[str, Form()],
    date_added: Annotated[date, Form(...)]
    ):

    try:
        # Perform update
        updated_inventory_info = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id4,
            document_id=item_id,
            data={"item_name": item_name,
                  "item_type": item_type,
                  "unit": unit,
                  "quantity_available": quantity_available,
                  "reorder_level": reorder_level,
                  "unit_price": unit_price,
                  "total_value": total_value,
                  "supplier_name": supplier_name,
                  "batch_number": batch_number,
                  "farm_id": farm_id,
                  "notes": notes,
                  "status": status,
                  "added_by": added_by,        
                  "date_added": date_added.isoformat()
            },
            permissions=[]
        )
        return {"message": "inventory info updated successfully", "user": updated_inventory_info}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")
    
@collection4_router.delete("/inventory/{item_id}")
def delete_inventory(item_id:str):
    try:
        db.delete_document(
            database_id=db_id,
            collection_id=db_collection_id4, 
            document_id=item_id)
        return {"message": f"User with ID {item_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))