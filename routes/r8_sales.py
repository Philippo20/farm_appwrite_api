from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from enum import Enum
from datetime import datetime, date, timezone
from html import escape
import os
import secrets
from urllib.parse import quote
from main import (
    db_id,
    db_collection_id1,
    db_collection_id7,
    db_collection_id8,
    db_collection_id17,
)
from db import db
from appwrite.id import ID
from fastapi.responses import HTMLResponse
from audit_utils import write_audit
from routes.r25_notifications import create_notification

collection8_router = APIRouter(tags=["Sales"])

class Status(str, Enum):
    PENDING = "Pending"
    IN_TRANSIT = "In Transit"
    DELIVERED = "Delivered"
    CANCELLED= "Cancelled"

class OfftakerStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


def _normalized(value):
    return str(value or "").strip().casefold()


def _catalog_key(value):
    return "".join(character for character in _normalized(value) if character.isalnum())


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


def _pricing_matches_fulfillment(pricing, fulfillment):
    variety = _catalog_key(fulfillment.get("plant_variety"))
    priced_variety = _catalog_key(pricing.get("crop_variety"))
    package = _catalog_key(fulfillment.get("packaging_type"))
    priced_package = _catalog_key(pricing.get("packaging"))
    variety_matches = bool(variety and priced_variety and variety == priced_variety)
    package_matches = bool(
        package
        and priced_package
        and (package == priced_package or package in priced_package or priced_package in package)
    )
    return variety_matches and package_matches


def _validated_sale_price(pricing_reference, price_tier, fulfillment):
    reference = str(pricing_reference or "").strip()
    pricing = None
    if reference:
        try:
            pricing = db.get_document(
                database_id=db_id,
                collection_id=db_collection_id17,
                document_id=reference,
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The selected sales price could not be found.",
            )
    else:
        prices = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id17,
        ).get("documents", [])
        pricing = next(
            (
                item
                for item in prices
                if _normalized(item.get("pricing_type")) == "hub_sale"
                and _normalized(item.get("status")) == "active"
                and _pricing_matches_fulfillment(item, fulfillment)
            ),
            None,
        )

    if pricing is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Configure an active Hub sale price for this crop variety and package before allocating it.",
        )
    if _normalized(pricing.get("pricing_type")) != "hub_sale":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only Hub sale pricing can be used for off-taker deliveries.",
        )
    if _normalized(pricing.get("status")) != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected Hub sale price is not active.",
        )
    if not _pricing_matches_fulfillment(pricing, fulfillment):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected price does not match the batch crop variety and package.",
        )

    tier = "Bulk" if _normalized(price_tier) == "bulk" else "Regular"
    price_key = "bulk_price" if tier == "Bulk" else "regular_price"
    unit_price = _number(pricing.get(price_key))
    if unit_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"The selected {tier.lower()} price must be greater than zero.",
        )
    return pricing, tier, unit_price


def _assigned_user(user_id, allowed_roles, label):
    reference = str(user_id or "").strip()
    if not reference:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Assign an active {label} before creating the delivery.",
        )
    try:
        user = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id1,
            document_id=reference,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The selected {label} could not be found.",
        )
    if _normalized(user.get("status") or "Active") != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The selected {label} is not active.",
        )
    if _normalized(user.get("role")) not in {_normalized(role) for role in allowed_roles}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"The selected user is not a valid {label}.",
        )
    return user


def _delivery_assignment(
    delivery_type,
    delivery_agent_id,
    delivery_provider,
    third_party_driver_name,
    delivery_plate_number,
):
    assignment_type = _normalized(delivery_type).replace(" ", "_").replace("-", "_")
    if assignment_type in {"third_party", "external"}:
        provider = str(delivery_provider or "").strip()
        driver_name = str(third_party_driver_name or "").strip()
        plate_number = str(delivery_plate_number or "").strip().upper()
        missing = []
        if not provider:
            missing.append("delivery provider")
        if not driver_name:
            missing.append("driver name")
        if not plate_number:
            missing.append("plate number")
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Enter the third-party {', '.join(missing)}.",
            )
        return {
            "delivery_type": "third_party",
            "delivery_provider": provider,
            "delivery_agent_id": "",
            "delivery_agent_name": driver_name,
            "delivery_vehicle": plate_number,
            "delivery_plate_number": plate_number,
        }, None

    delivery_agent = _assigned_user(
        delivery_agent_id,
        {"driver", "delivery_agent"},
        "Delivery Agent",
    )
    vehicle = str(delivery_agent.get("vehicle") or "Pending assignment").strip()
    return {
        "delivery_type": "internal",
        "delivery_provider": "Farm Estates",
        "delivery_agent_id": str(delivery_agent.get("$id") or delivery_agent_id),
        "delivery_agent_name": str(delivery_agent.get("name") or "Delivery Agent"),
        "delivery_vehicle": vehicle,
        "delivery_plate_number": vehicle,
    }, delivery_agent


def _new_invoice_number():
    return f"INV-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"


def _public_invoice_url(sale_id):
    ui_url = os.getenv("APP_UI_URL", "https://apps.farmestates.farm").strip().rstrip("/")
    return f"{ui_url}/#/sales-invoice?id={quote(str(sale_id or ''), safe='')}"


def _notify_delivery_assignment(sale, recipient, responsibility):
    recipient_id = str(recipient.get("$id") or "").strip()
    if not recipient_id:
        return
    invoice_number = str(sale.get("invoice_number") or "Invoice")
    third_party = _normalized(sale.get("delivery_type")) == "third_party"
    delivery_summary = (
        f"Third-party delivery: {sale.get('delivery_provider', '')}, driver "
        f"{sale.get('delivery_agent_name', '')}, plate "
        f"{sale.get('delivery_plate_number', '')}. "
        if third_party
        else f"Internal driver: {sale.get('delivery_agent_name', '')}, vehicle "
        f"{sale.get('delivery_vehicle', '')}. "
    )
    create_notification(
        recipient_id=recipient_id,
        recipient_name=str(recipient.get("name") or responsibility),
        title=f"Delivery assigned - {invoice_number}",
        message=(
            f"{sale.get('package_count', 0)} packs from batch "
            f"{sale.get('batch_number', '')} are assigned to you for "
            f"{sale.get('buyer_name', 'the off-taker')}. {delivery_summary}"
            "Open and print the invoice, "
            "then obtain the off-taker signature at handover. "
            f"Invoice: {_public_invoice_url(sale.get('$id'))}"
        ),
        notification_type="delivery",
        priority="high",
        related_task_id=str(sale.get("$id") or ""),
    )

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
        scheduled_for: Annotated[datetime | None, Form()] = None,
        pricing_id: Annotated[str, Form()] = "",
        price_tier: Annotated[str, Form()] = "Regular",
        sales_person_id: Annotated[str, Form()] = "",
        delivery_agent_id: Annotated[str, Form()] = "",
        receipt_image: Annotated[str, Form()] = "",
        receipt_number: Annotated[str, Form()] = "",
        delivery_type: Annotated[str, Form()] = "internal",
        delivery_provider: Annotated[str, Form()] = "",
        third_party_driver_name: Annotated[str, Form()] = "",
        delivery_plate_number: Annotated[str, Form()] = ""
        ):
    fulfillment, _ = _validated_allocation(
        fulfillment_id or batch_number or batch_id,
        package_count,
    )
    canonical_batch = _batch_number(fulfillment)
    unit_weight = _number(fulfillment.get("packaging_weight"))
    allocated_weight = round(unit_weight * package_count, 6)
    pricing, resolved_tier, unit_price = _validated_sale_price(
        pricing_id,
        price_tier,
        fulfillment,
    )
    calculated_total = round(unit_price * package_count, 2)
    sales_person = _assigned_user(
        sales_person_id,
        {"sales_person", "sales_personnel"},
        "Sales Personnel",
    )
    delivery_assignment, delivery_agent = _delivery_assignment(
        delivery_type,
        delivery_agent_id,
        delivery_provider,
        third_party_driver_name,
        delivery_plate_number,
    )
    invoice_number = _new_invoice_number()
    invoice_generated_at = datetime.now(timezone.utc).isoformat()
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
        "pricing_id": str(pricing.get("$id") or pricing_id),
        "price_tier": resolved_tier,
        "unit_price": unit_price,
        "invoice_number": invoice_number,
        "invoice_generated_at": invoice_generated_at,
        "sales_person_id": str(sales_person.get("$id") or sales_person_id),
        "sales_person_name": str(sales_person.get("name") or "Sales Personnel"),
        **delivery_assignment,
        "buyer_id": buyer_id,
        "off_taker_id": off_taker_id,
        "buyer_name": buyer_name,
        "delivered_by": delivered_by,
        "delivered_at": delivered_at.isoformat(),
        "scheduled_for": scheduled_value.isoformat(),
        "quantity_delivered": allocated_weight,
        "total_amount": calculated_total,
        "paid": paid,
        "payment_mode": payment_mode,
        "receipt_image": receipt_image.strip() or "Pending signature",
        "receipt_number": receipt_number.strip() or invoice_number,
        "payment_date": payment_date.isoformat(),
        "created_by": created_by,
        "status": status.value,
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
    _notify_delivery_assignment(sales_create, sales_person, "Sales Personnel")
    if delivery_agent is not None and str(delivery_agent.get("$id") or "") != str(sales_person.get("$id") or ""):
        _notify_delivery_assignment(sales_create, delivery_agent, "Delivery Agent")
    write_audit(
        action_type="Create",
        collection_name="Sales",
        performed_by_id=created_by,
        performed_by_role=created_by_role.strip() or "sales_manager",
        action_details=(
            f"Allocated {package_count} packs ({allocated_weight:.2f} kg) "
            f"from batch {canonical_batch} to {buyer_name} at "
            f"GHS {unit_price:.2f} per pack (GHS {calculated_total:.2f})"
        ),
        new_data=sales_info
    )

    return {
        "message": "Delivery created and invoice generated successfully",
        "sales_id": sales_create["$id"],
        "sale": sales_create,
        "invoice_url": _public_invoice_url(sales_create["$id"])
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


@collection8_router.get("/sales/{sale_id}/invoice", response_class=HTMLResponse)
def get_sales_invoice(sale_id: str):
    try:
        sale = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id8,
            document_id=sale_id,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales invoice not found.",
        )

    def value(key, fallback="-"):
        text = str(sale.get(key) or "").strip()
        return escape(text or fallback)

    invoice_number = value("invoice_number", value("receipt_number", sale_id))
    generated_at = value("invoice_generated_at", value("delivered_at"))
    package_count = _integer(sale.get("package_count"))
    unit_price = _number(sale.get("unit_price"))
    total_amount = _number(sale.get("total_amount"))
    quantity = _number(sale.get("quantity_delivered"))
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{invoice_number} | Farm Estates Ltd</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #eef2f0; color: #17211b; font-family: Arial, sans-serif; }}
    .toolbar {{ max-width: 900px; margin: 18px auto 0; display: flex; justify-content: flex-end; }}
    .print {{ border: 0; border-radius: 8px; padding: 12px 20px; color: #fff; background: #36a852; font-weight: 700; cursor: pointer; }}
    .invoice {{ width: min(900px, calc(100% - 28px)); margin: 14px auto 32px; background: #fff; padding: 42px; box-shadow: 0 8px 28px rgba(18,43,28,.12); }}
    .header {{ display: flex; justify-content: space-between; gap: 24px; padding-bottom: 24px; border-bottom: 3px solid #36a852; }}
    h1 {{ margin: 0; font-size: 30px; }}
    .brand {{ color: #23883d; font-weight: 800; font-size: 22px; }}
    .muted {{ color: #66736b; font-size: 13px; line-height: 1.5; }}
    .right {{ text-align: right; }}
    .parties {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin: 28px 0; }}
    .label {{ color: #66736b; font-size: 12px; text-transform: uppercase; font-weight: 700; margin-bottom: 7px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
    th {{ background: #edf8f0; color: #276c39; text-align: left; padding: 13px 10px; font-size: 12px; }}
    td {{ padding: 15px 10px; border-bottom: 1px solid #e4e9e6; vertical-align: top; }}
    .number {{ text-align: right; }}
    .total {{ margin: 24px 0 36px auto; width: min(360px, 100%); }}
    .total div {{ display: flex; justify-content: space-between; padding: 8px 0; }}
    .grand {{ border-top: 2px solid #17211b; font-size: 19px; font-weight: 800; }}
    .assignment {{ padding: 16px; background: #f6f8f7; border-left: 4px solid #36a852; line-height: 1.7; }}
    .signatures {{ display: grid; grid-template-columns: 1fr 1fr; gap: 55px; margin-top: 80px; }}
    .signature {{ border-top: 1px solid #17211b; padding-top: 9px; font-size: 13px; }}
    .footer {{ margin-top: 40px; border-top: 1px solid #e4e9e6; padding-top: 16px; text-align: center; }}
    @media (max-width: 620px) {{ .invoice {{ padding: 24px; }} .header, .parties, .signatures {{ grid-template-columns: 1fr; display: grid; }} .right {{ text-align: left; }} }}
    @page {{ size: A4 portrait; margin: 12mm; }}
    @media print {{ body {{ background: #fff; }} .toolbar {{ display: none; }} .invoice {{ width: 100%; margin: 0; padding: 22px; box-shadow: none; break-inside: avoid; }} }}
  </style>
</head>
<body>
  <div class="toolbar"><button class="print" onclick="window.print()">Print invoice</button></div>
  <main class="invoice">
    <header class="header">
      <div><div class="brand">FARM ESTATES LTD</div><div class="muted">Packaged produce delivery invoice</div></div>
      <div class="right"><h1>INVOICE</h1><strong>{invoice_number}</strong><div class="muted">Generated: {generated_at}</div></div>
    </header>
    <section class="parties">
      <div><div class="label">Deliver to</div><strong>{value('buyer_name', 'Off-taker')}</strong><div class="muted">{value('delivery_address')}</div></div>
      <div><div class="label">Delivery assignment</div><strong>{value('sales_person_name', 'Sales Personnel')}</strong><div class="muted">Method: {"Third-party delivery" if _normalized(sale.get('delivery_type')) == 'third_party' else "Internal fleet"}</div><div class="muted">Provider: {value('delivery_provider', 'Farm Estates')}</div><div class="muted">Driver: {value('delivery_agent_name', 'Unassigned')}</div><div class="muted">Plate / vehicle: {value('delivery_plate_number', value('delivery_vehicle', 'Pending assignment'))}</div><div class="muted">Scheduled: {value('scheduled_for')}</div></div>
    </section>
    <table>
      <thead><tr><th>Batch / Product</th><th>Package</th><th class="number">Packs</th><th class="number">Unit price</th><th class="number">Amount</th></tr></thead>
      <tbody><tr><td><strong>{value('batch_number')}</strong><div class="muted">{value('crop_variety')} | {quantity:.2f} kg</div></td><td>{value('package_type')}<div class="muted">{value('price_tier', 'Regular')} price</div></td><td class="number">{package_count}</td><td class="number">GHS {unit_price:.2f}</td><td class="number"><strong>GHS {total_amount:.2f}</strong></td></tr></tbody>
    </table>
    <section class="total"><div><span>Subtotal</span><span>GHS {total_amount:.2f}</span></div><div class="grand"><span>Total</span><span>GHS {total_amount:.2f}</span></div><div class="muted">Payment: {value('payment_mode')} | {"Paid" if sale.get('paid') is True else "Payment due"}</div></section>
    <section class="assignment"><strong>Handover instructions</strong><br>{value('delivery_notes', 'Inspect the packs, sign this invoice, and return the signed copy to Farm Estates Ltd.')}</section>
    <section class="signatures"><div class="signature">Off-taker name, signature and date</div><div class="signature">Sales Personnel / Delivery Agent signature and date</div></section>
    <footer class="footer muted">This document confirms physical handover only when signed by the receiving off-taker.</footer>
  </main>
</body>
</html>"""
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'inline; filename="{invoice_number}.html"'},
    )
    
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
    scheduled_for: Annotated[datetime | None, Form()] = None,
    pricing_id: Annotated[str, Form()] = "",
    price_tier: Annotated[str, Form()] = "Regular",
    sales_person_id: Annotated[str, Form()] = "",
    delivery_agent_id: Annotated[str, Form()] = "",
    receipt_image: Annotated[str, Form()] = "",
    receipt_number: Annotated[str, Form()] = "",
    delivery_type: Annotated[str, Form()] = "internal",
    delivery_provider: Annotated[str, Form()] = "",
    third_party_driver_name: Annotated[str, Form()] = "",
    delivery_plate_number: Annotated[str, Form()] = ""
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
        pricing, resolved_tier, unit_price = _validated_sale_price(
            pricing_id,
            price_tier,
            fulfillment,
        )
        calculated_total = round(unit_price * package_count, 2)
        sales_person = _assigned_user(
            sales_person_id,
            {"sales_person", "sales_personnel"},
            "Sales Personnel",
        )
        delivery_assignment, delivery_agent = _delivery_assignment(
            delivery_type,
            delivery_agent_id,
            delivery_provider,
            third_party_driver_name,
            delivery_plate_number,
        )
        scheduled_value = scheduled_for or delivered_at
        invoice_number = str(previous_sale.get("invoice_number") or _new_invoice_number())
        update_data = {"batch_id": canonical_batch,
                  "batch_number": canonical_batch,
                  "fulfillment_id": str(fulfillment.get("$id") or fulfillment_id),
                  "crop_variety": str(
                      fulfillment.get("plant_variety") or fulfillment.get("plant_type") or ""
                  ).strip(),
                  "package_type": str(fulfillment.get("packaging_type") or "").strip(),
                  "package_count": package_count,
                  "unit_weight_kg": unit_weight,
                  "pricing_id": str(pricing.get("$id") or pricing_id),
                  "price_tier": resolved_tier,
                  "unit_price": unit_price,
                  "invoice_number": invoice_number,
                  "invoice_generated_at": str(
                      previous_sale.get("invoice_generated_at")
                      or datetime.now(timezone.utc).isoformat()
                  ),
                  "sales_person_id": str(sales_person.get("$id") or sales_person_id),
                  "sales_person_name": str(sales_person.get("name") or "Sales Personnel"),
                  **delivery_assignment,
                  "buyer_id": buyer_id,
                  "off_taker_id": off_taker_id,
                  "buyer_name": buyer_name,
                  "delivered_by": delivered_by,
                  "delivered_at": delivered_at.isoformat(),
                  "scheduled_for": scheduled_value.isoformat(),
                  "quantity_delivered": allocated_weight,
                  "total_amount": calculated_total,
                  "paid": paid,
                  "payment_mode": payment_mode,
                  "receipt_image": receipt_image.strip() or str(
                      previous_sale.get("receipt_image") or "Pending signature"
                  ),
                  "receipt_number": receipt_number.strip() or invoice_number,
                  "payment_date": payment_date.isoformat(),
                  "created_by": created_by,
                  "status": status.value,
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
        assignment_changed = any(
            str(previous_sale.get(key) or "") != str(update_data.get(key) or "")
            for key in (
                "sales_person_id",
                "delivery_type",
                "delivery_provider",
                "delivery_agent_id",
                "delivery_agent_name",
                "delivery_plate_number",
            )
        )
        if assignment_changed:
            _notify_delivery_assignment(updated_sales_info, sales_person, "Sales Personnel")
            if delivery_agent is not None and str(delivery_agent.get("$id") or "") != str(sales_person.get("$id") or ""):
                _notify_delivery_assignment(updated_sales_info, delivery_agent, "Delivery Agent")
        elif _normalized(previous_sale.get("status")) != _normalized(status.value):
            create_notification(
                recipient_id=str(sales_person.get("$id") or sales_person_id),
                recipient_name=str(sales_person.get("name") or "Sales Personnel"),
                title=f"Delivery {status.value.lower()} - {invoice_number}",
                message=(
                    f"The delivery for {buyer_name} has been updated to "
                    f"{status.value}."
                ),
                notification_type="delivery",
                priority="high" if status == Status.DELIVERED else "normal",
                related_task_id=sale_id,
            )
        write_audit(
            action_type="Update",
            collection_name="Sales",
            performed_by_id=created_by,
            performed_by_role=created_by_role.strip() or "sales_manager",
            action_details=(
                f"Updated delivery allocation for batch {canonical_batch}: "
                f"{package_count} packs ({allocated_weight:.2f} kg) at "
                f"GHS {unit_price:.2f} per pack (GHS {calculated_total:.2f})"
            ),
            previous_data=previous_sale,
            new_data=update_data
        )
        return {"message": "Sales info updated successfully", "user": updated_sales_info}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


@collection8_router.patch("/sales/{sale_id}/handover")
def update_sales_handover(
    sale_id: str,
    actor_id: Annotated[str, Form()],
    actor_name: Annotated[str, Form()],
    status_value: Annotated[Status, Form()],
    delivery_notes: Annotated[str, Form()] = "",
    receipt_number: Annotated[str, Form()] = "",
    paid: Annotated[bool, Form()] = False,
    payment_mode: Annotated[str, Form()] = "",
):
    """Record the off-taker handover without re-running allocation validation."""
    try:
        sale = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id8,
            document_id=sale_id,
        )
        actor = _assigned_user(
            actor_id,
            {"sales_person", "sales_personnel"},
            "Sales Personnel",
        )
        resolved_actor_name = str(
            actor.get("name") or actor_name or "Sales Personnel"
        )
        assigned_id = str(sale.get("sales_person_id") or "").strip()
        if assigned_id and _normalized(actor_id) != _normalized(assigned_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This delivery is assigned to another Sales Personnel user.",
            )

        update_data = {
            "status": status_value.value,
            "delivery_notes": str(delivery_notes or "").strip(),
            "receipt_number": str(receipt_number or "").strip()
            or str(sale.get("receipt_number") or sale.get("invoice_number") or ""),
            "paid": bool(paid),
            "payment_mode": str(payment_mode or "").strip(),
        }
        if status_value == Status.DELIVERED:
            completed_at = datetime.now(timezone.utc).isoformat()
            update_data["delivered_at"] = completed_at
            update_data["completed_at"] = completed_at
            if paid:
                update_data["payment_date"] = date.today().isoformat()

        updated_sale = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id8,
            document_id=sale_id,
            data=update_data,
        )

        manager_id = str(sale.get("created_by") or "").strip()
        if manager_id and _normalized(manager_id) != _normalized(actor_id):
            manager_name = "Sales Manager"
            try:
                manager = db.get_document(
                    database_id=db_id,
                    collection_id=db_collection_id1,
                    document_id=manager_id,
                )
                manager_name = str(manager.get("name") or manager_name)
            except Exception:
                pass
            create_notification(
                recipient_id=manager_id,
                recipient_name=manager_name,
                title=f"Delivery {status_value.value.lower()} - {sale.get('invoice_number', 'Invoice')}",
                message=(
                    f"{resolved_actor_name} updated the delivery for "
                    f"{sale.get('buyer_name', 'the off-taker')} to {status_value.value}."
                ),
                notification_type="delivery",
                priority="high" if status_value == Status.DELIVERED else "normal",
                related_task_id=sale_id,
            )

        write_audit(
            action_type="Update",
            collection_name="Sales",
            performed_by_id=actor_id,
            performed_by_role="sales_personnel",
            action_details=(
                f"Updated delivery {sale.get('invoice_number', sale_id)} "
                f"handover status to {status_value.value}"
            ),
            previous_data=sale,
            new_data=update_data,
        )
        return {
            "message": "Delivery handover updated successfully",
            "sale": updated_sale,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not update delivery handover: {error}",
        )
    
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
