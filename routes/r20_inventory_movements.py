from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException
from appwrite.id import ID
from appwrite.query import Query

from main import db_id, db_collection_id20
from db import db
from audit_utils import write_audit


collection20_router = APIRouter(tags=["Inventory Movements"])


class MovementType(str, Enum):
    STOCK_IN = "stock_in"
    STOCK_OUT = "stock_out"
    ADJUSTMENT = "adjustment"


@collection20_router.get("/inventory/movements")
def get_inventory_movements(limit: int = 100, offset: int = 0):
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id20,
            queries=[Query.limit(limit), Query.offset(offset)],
        )
        docs = result.get("documents", [])
        return {"count": len(docs), "users": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@collection20_router.post("/inventory/movements")
def create_inventory_movement(
    item_id: Annotated[str, Form()],
    item_name: Annotated[str, Form()],
    movement_type: Annotated[MovementType, Form()],
    quantity: Annotated[float, Form()],
    unit: Annotated[str, Form()],
    actor: Annotated[str, Form()],
    farm_id: Annotated[str, Form()] = "",
    farm_name: Annotated[str, Form()] = "Unassigned Farm",
    note: Annotated[str, Form()] = "",
):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

    movement = {
        "movement_id": ID.unique(),
        "item_id": item_id,
        "item_name": item_name,
        "farm_id": farm_id,
        "farm_name": farm_name,
        "movement_type": movement_type.value,
        "quantity": quantity,
        "unit": unit,
        "actor": actor,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    created = db.create_document(
        database_id=db_id,
        collection_id=db_collection_id20,
        document_id=ID.unique(),
        data=movement,
    )
    write_audit(
        action_type="Create",
        collection_name="Inventory Movements",
        performed_by_id=actor,
        action_details=f"Created {movement_type.value} movement for {item_name}",
        new_data=movement,
    )
    return {"message": "Inventory movement recorded successfully", "movement": created}
