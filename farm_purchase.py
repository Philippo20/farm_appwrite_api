"""Persist farm-owner revenue separately from the hub's off-taker sales."""
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import HTTPException
from document_paging import list_all_documents


def normalized(value):
    return str(getattr(value, "value", value) or "").strip().casefold()


def number(value):
    try:
        result = Decimal(str(value or 0))
        return result if result.is_finite() and result >= 0 else Decimal(0)
    except (InvalidOperation, ValueError):
        return Decimal(0)


def purchase_snapshot(record):
    try:
        value = json.loads(record.get("farm_purchase") or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def accepted(record):
    if normalized(record.get("delivery_status")) in {"cancelled", "rejected", "on hold"}:
        return False
    return normalized(record.get("delivery_status")) == "delivered" or normalized(record.get("status")) in {
        "packaging", "packaged", "sent to sales", "completed"
    }


def receipt_identity(record, batch=None, farms=()):
    batch = batch or {}
    farm_id = str(batch.get("farmID") or batch.get("farm_id") or record.get("farm_id") or "").strip()
    farm_name = str(batch.get("farm_name") or record.get("farm_name") or "").strip()
    if not farm_id:
        matches = [farm for farm in farms if normalized(farm.get("name") or farm.get("farm_name")) == normalized(farm_name)]
        if len(matches) == 1:
            farm_id = str(matches[0].get("$id") or matches[0].get("farm_id") or "")
    return {
        "farm_id": farm_id, "farm_name": farm_name,
        "plant_type": str(batch.get("plant_name") or record.get("plant_type") or "").strip(),
        "crop_variety": str(batch.get("plant_variety") or record.get("plant_variety") or "").strip(),
        "batch_number": str(record.get("batch_number") or "").strip(),
    }


def choose_price(identity, prices):
    if not identity["farm_id"] or not identity["plant_type"]:
        return None
    candidates = [price for price in prices
        if normalized(price.get("pricing_type") or "hub_purchase") == "hub_purchase"
        and normalized(price.get("status")) == "active"
        and str(price.get("farm_id") or "") == identity["farm_id"]
        and normalized(price.get("plant_type")) == normalized(identity["plant_type"])
        and normalized(price.get("crop_variety")) in {"", normalized(identity["crop_variety"])}]
    exact = [price for price in candidates if normalized(price.get("crop_variety")) == normalized(identity["crop_variety"])]
    candidates = exact or candidates
    # Conflicting active prices are not guessed: leave the receipt unpriced.
    return candidates[0] if len(candidates) == 1 else None


def make_snapshot(record, identity, price):
    if price is None:
        return None
    tier = "Bulk" if normalized(price.get("owner_price_tier")) == "bulk" else "Regular"
    rate = number(price.get("bulk_price" if tier == "Bulk" else "regular_price"))
    unit = normalized(price.get("unit") or "kg")
    weight = number(record.get("total_weight"))
    if unit == "kg":
        quantity = weight
    elif unit == "g":
        quantity = weight * 1000
    elif unit in {"head", "heads"}:
        quantity = number(record.get("total_heads"))
    else:
        # Intake does not record crates/boxes/bunches. Never treat kg as boxes.
        return None
    if quantity <= 0 or rate <= 0:
        return None
    return {**identity, "pricing_id": str(price.get("$id") or ""),
        "price_tier": tier, "unit": unit, "quantity": float(quantity),
        "unit_price": float(rate), "total_amount": float((quantity * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "currency": "GHS", "accepted_weight_kg": float(weight),
        "accepted_heads": float(number(record.get("total_heads"))),
        "recorded_at": datetime.now(timezone.utc).isoformat()}


def capture_purchase(db, record, previous=None, batch=None):
    from main import db_id, db_collection_id2, db_collection_id5, db_collection_id17
    previous = previous or {}
    saved = purchase_snapshot(previous)
    if saved:
        if (normalized(record.get("batch_number")) != normalized(saved.get("batch_number")) or
            normalized(record.get("farm_name")) != normalized(saved.get("farm_name")) or
            number(record.get("total_weight")) != number(saved.get("accepted_weight_kg")) or
            number(record.get("total_heads")) != number(saved.get("accepted_heads"))):
            raise HTTPException(409, "This receipt has a saved farm purchase valuation. Its batch, farm and accepted quantities cannot be changed.")
        return {"farm_purchase": previous["farm_purchase"]}
    if not accepted(record):
        return {}
    if batch is None:
        batches = list_all_documents(db, database_id=db_id, collection_id=db_collection_id5)["documents"]
        batch = next((item for item in batches if normalized(record.get("batch_number")) in {
            normalized(item.get("batch_no")), normalized(item.get("batch_id")), normalized(item.get("$id"))}), None)
    farms = list_all_documents(db, database_id=db_id, collection_id=db_collection_id2)["documents"]
    prices = list_all_documents(db, database_id=db_id, collection_id=db_collection_id17)["documents"]
    identity = receipt_identity(record, batch, farms)
    snapshot = make_snapshot(record, identity, choose_price(identity, prices))
    return {"farm_purchase": json.dumps(snapshot, separators=(",", ":"))} if snapshot else {}


def value_unpriced_receipts(db, pricing):
    from main import db_id, db_collection_id7
    if normalized(pricing.get("pricing_type")) != "hub_purchase":
        return {"valued_receipts": 0, "pending_receipts": 0}
    try:
        receipts = list_all_documents(db, database_id=db_id, collection_id=db_collection_id7)["documents"]
    except Exception:
        return {"valued_receipts": 0, "pending_receipts": 0,
                "valuation_warning": "Pricing saved, but existing receipts could not be loaded. Retry valuation later."}
    valued = pending = 0
    seen_batches = {normalized(item.get("batch_number")) for item in receipts if purchase_snapshot(item)}
    for receipt in receipts:
        if purchase_snapshot(receipt) or not accepted(receipt):
            continue
        # Each capture resolves the active price by farm, crop and variety, never
        # overriding another farm's rate or any already saved valuation.
        if normalized(receipt.get("farm_name")) != normalized(pricing.get("farm_name")):
            continue
        if normalized(receipt.get("plant_type")) != normalized(pricing.get("plant_type")):
            continue
        if pricing.get("crop_variety") and normalized(receipt.get("plant_variety")) != normalized(pricing.get("crop_variety")):
            continue
        batch_key = normalized(receipt.get("batch_number"))
        if batch_key and batch_key in seen_batches:
            continue
        try:
            data = capture_purchase(db, receipt)
            if data and purchase_snapshot(data).get("pricing_id") == pricing.get("$id"):
                db.update_document(database_id=db_id, collection_id=db_collection_id7,
                    document_id=receipt["$id"], data=data)
                valued += 1
                if batch_key:
                    seen_batches.add(batch_key)
                try:
                    from audit_utils import write_audit
                    write_audit(action_type="Update", collection_name="Fulfillment",
                        action_details="Initial farm purchase valuation applied to unpriced receipt",
                        previous_data=receipt, new_data=data)
                except Exception:
                    pass  # Valuation has already been saved; do not count it twice.
            else:
                pending += 1
        except Exception:
            pending += 1
    return {"valued_receipts": valued, "pending_receipts": pending}
