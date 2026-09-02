import hashlib
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from appwrite.exception import AppwriteException
from appwrite.id import ID
from appwrite.query import Query
from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel, Field

from audit_utils import write_audit
from db import db
from main import (
    db_collection_id5,
    db_collection_id30,
    db_collection_id31,
    db_collection_id32,
    db_collection_id33,
    db_id,
)


traceability_router = APIRouter()
SETTINGS_ID = "global"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _documents(collection_id: str) -> List[Dict[str, Any]]:
    result = db.list_documents(
        database_id=db_id,
        collection_id=collection_id,
        queries=[Query.limit(5000)],
    )
    return list(result.get("documents") or [])


def _default_settings() -> Dict[str, Any]:
    return {
        "config_id": SETTINGS_ID,
        "public_site_url": "https://app.farmestates.farm",
        "brand_name": "Farm Estates Ltd",
        "headline": "Know where your food comes from",
        "support_email": "",
        "primary_color": "#4CAF50",
        "secondary_color": "#29B6F6",
        "logo_url": "",
        "privacy_notice_url": "",
        "lookup_enabled": True,
        "show_farm": True,
        "show_location": True,
        "show_dates": True,
        "show_quality": True,
        "show_journey": True,
        "analytics_enabled": True,
        "promotions_enabled": True,
        "retention_days": 365,
        "updated_by": "system",
        "updated_at": _now(),
    }


def _settings() -> Dict[str, Any]:
    try:
        return db.get_document(
            database_id=db_id,
            collection_id=db_collection_id30,
            document_id=SETTINGS_ID,
        )
    except AppwriteException as error:
        if getattr(error, "code", None) != 404:
            raise
        return db.create_document(
            database_id=db_id,
            collection_id=db_collection_id30,
            document_id=SETTINGS_ID,
            data=_default_settings(),
        )


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _find_trace(*, batch_number: str = "", token: str = "") -> Optional[Dict[str, Any]]:
    needle = _clean(batch_number).casefold()
    token_needle = _clean(token).casefold()
    for trace in _documents(db_collection_id31):
        if not trace.get("published"):
            continue
        if needle and _clean(trace.get("batch_number")).casefold() == needle:
            return trace
        if token_needle and _clean(trace.get("public_token")).casefold() == token_needle:
            return trace
    return None


def _find_batch(batch_id: str) -> Dict[str, Any]:
    try:
        return db.get_document(
            database_id=db_id,
            collection_id=db_collection_id5,
            document_id=batch_id,
        )
    except AppwriteException as error:
        raise HTTPException(status_code=404, detail="Batch not found") from error


def _ip_hash(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    salt = os.getenv("TRACEABILITY_IP_SALT") or "farmestates-traceability"
    return hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()


def _record_event(
    request: Request,
    *,
    event_type: str,
    metadata: Dict[str, Any],
    trace: Optional[Dict[str, Any]] = None,
) -> str:
    event_id = ID.unique()
    db.create_document(
        database_id=db_id,
        collection_id=db_collection_id33,
        document_id=event_id,
        data={
            "event_id": event_id,
            "event_type": event_type,
            "trace_id": _clean((trace or {}).get("trace_id")),
            "batch_number": _clean(metadata.get("batch_number") or (trace or {}).get("batch_number")),
            "promotion_id": _clean(metadata.get("promotion_id")),
            "anonymous_session": _clean(metadata.get("session_id"))[:225],
            "ip_hash": _ip_hash(request),
            "country": _clean(metadata.get("country"))[:120],
            "region": _clean(metadata.get("region"))[:160],
            "city": _clean(metadata.get("city"))[:160],
            "device_type": (_clean(metadata.get("device_type")) or "unknown")[:80],
            "referrer": _clean(metadata.get("referrer"))[:1000],
            "user_agent": (_clean(metadata.get("user_agent")) or _clean(request.headers.get("user-agent")))[:1000],
            "occurred_at": _now(),
        },
    )
    return event_id


def _active_promotion(trace: Dict[str, Any], region: str) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    candidates = []
    for promo in _documents(db_collection_id32):
        if promo.get("status") != "active":
            continue
        target_batch = _clean(promo.get("target_batch_id"))
        target_region = _clean(promo.get("target_region")).casefold()
        if target_batch and target_batch != _clean(trace.get("batch_id")):
            continue
        if target_region and target_region != _clean(region).casefold():
            continue
        try:
            if promo.get("start_at") and datetime.fromisoformat(str(promo["start_at"]).replace("Z", "+00:00")) > now:
                continue
            if promo.get("end_at") and datetime.fromisoformat(str(promo["end_at"]).replace("Z", "+00:00")) < now:
                continue
        except ValueError:
            continue
        candidates.append(promo)
    if not candidates:
        return None
    candidates.sort(key=lambda item: int(item.get("priority") or 0), reverse=True)
    promo = candidates[0]
    return {
        "id": promo.get("promotion_id") or promo.get("$id"),
        "title": promo.get("title", ""),
        "message": promo.get("message", ""),
        "image_url": promo.get("image_url", ""),
        "destination_url": promo.get("destination_url", ""),
    }


def _public_config(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "brand_name": config.get("brand_name"),
        "headline": config.get("headline"),
        "support_email": config.get("support_email"),
        "primary_color": config.get("primary_color"),
        "secondary_color": config.get("secondary_color"),
        "logo_url": config.get("logo_url"),
        "privacy_notice_url": config.get("privacy_notice_url"),
        "lookup_enabled": config.get("lookup_enabled", True),
    }


def _public_trace(trace: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    batch = _find_batch(_clean(trace.get("batch_id")))
    result = {
        "verified": trace.get("recall_status") != "recalled",
        "batch_number": trace.get("batch_number"),
        "public_token": trace.get("public_token"),
        "product_name": trace.get("product_name"),
        "variety": trace.get("variety"),
        "packaging": trace.get("packaging_label"),
        "message": trace.get("public_message"),
        "recall_status": trace.get("recall_status", "none"),
    }
    if config.get("show_farm", True):
        result["farm_name"] = trace.get("farm_name")
    if config.get("show_location", True):
        result["farm_region"] = trace.get("farm_region")
    if config.get("show_dates", True):
        result["production_dates"] = {
            "started": batch.get("start_date"),
            "expected_or_completed": batch.get("end_date"),
        }
    if config.get("show_quality", True):
        result["quality_status"] = trace.get("quality_status", "Verified")
    if config.get("show_journey", True):
        result["journey"] = [
            {"stage": "Production", "status": batch.get("production_status", "Recorded")},
            {"stage": "Quality", "status": trace.get("quality_status", "Verified")},
            {"stage": "Packaging", "status": trace.get("packaging_label") or "Recorded"},
        ]
    return result


class SettingsPayload(BaseModel):
    public_site_url: str
    brand_name: str
    headline: str
    support_email: str = ""
    primary_color: str = "#4CAF50"
    secondary_color: str = "#29B6F6"
    logo_url: str = ""
    privacy_notice_url: str = ""
    lookup_enabled: bool = True
    show_farm: bool = True
    show_location: bool = True
    show_dates: bool = True
    show_quality: bool = True
    show_journey: bool = True
    analytics_enabled: bool = True
    promotions_enabled: bool = True
    retention_days: int = Field(default=365, ge=30, le=1825)
    updated_by: str = "system"


class PublishPayload(BaseModel):
    published: bool = True
    public_message: str = ""
    farm_region: str = ""
    packaging_label: str = ""
    quality_status: str = "Verified"
    recall_status: str = "none"
    actor_id: str = "system"
    actor_role: str = "admin"


class PromotionPayload(BaseModel):
    title: str
    message: str
    image_url: str = ""
    destination_url: str = ""
    status: str = "draft"
    target_batch_id: str = ""
    target_region: str = ""
    priority: int = Field(default=0, ge=0, le=100)
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    actor_id: str = "system"
    actor_role: str = "admin"


class LookupPayload(BaseModel):
    batch_number: str
    session_id: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    device_type: str = "unknown"
    referrer: str = ""
    user_agent: str = ""


class EventPayload(BaseModel):
    event_type: str
    public_token: str = ""
    batch_number: str = ""
    promotion_id: str = ""
    session_id: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    device_type: str = "unknown"
    referrer: str = ""
    user_agent: str = ""


@traceability_router.get("/traceability/overview", tags=["Traceability Admin"])
def traceability_overview():
    try:
        config = _settings()
        batches = _documents(db_collection_id5)
        traces = _documents(db_collection_id31)
        promotions = _documents(db_collection_id32)
        events = _documents(db_collection_id33)
        trace_by_batch = {_clean(item.get("batch_id")): item for item in traces}
        product_rows = []
        for batch in batches:
            batch_id = _clean(batch.get("batch_id") or batch.get("$id"))
            trace = trace_by_batch.get(batch_id, {})
            product_rows.append({
                "batch_id": batch_id,
                "batch_number": batch.get("batch_no", ""),
                "product_name": batch.get("plant_name", ""),
                "variety": batch.get("plant_variety", ""),
                "farm_name": batch.get("farm_name", ""),
                "production_status": batch.get("production_status", ""),
                "start_date": batch.get("start_date"),
                "end_date": batch.get("end_date"),
                "published": bool(trace.get("published")),
                "public_token": trace.get("public_token", ""),
                "public_url": f"{str(config.get('public_site_url') or '').rstrip('/')}/product/{trace.get('public_token')}" if trace.get("public_token") else "",
                "scan_count": int(trace.get("scan_count") or 0),
                "quality_status": trace.get("quality_status", "Verified"),
                "recall_status": trace.get("recall_status", "none"),
                "public_message": trace.get("public_message", ""),
                "farm_region": trace.get("farm_region", ""),
                "packaging_label": trace.get("packaging_label", ""),
            })
        unique_visitors = len({_clean(event.get("anonymous_session")) or _clean(event.get("ip_hash")) for event in events})
        metrics = {
            "published_products": sum(1 for item in traces if item.get("published")),
            "total_scans": sum(1 for item in events if item.get("event_type") == "lookup_success"),
            "unique_visitors": unique_visitors,
            "active_promotions": sum(1 for item in promotions if item.get("status") == "active"),
            "failed_lookups": sum(1 for item in events if item.get("event_type") == "lookup_failed"),
        }
        return {
            "settings": config,
            "metrics": metrics,
            "batches": product_rows,
            "promotions": promotions,
            "events": sorted(events, key=lambda item: str(item.get("occurred_at") or ""), reverse=True)[:100],
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not load traceability console: {error}") from error


@traceability_router.put("/traceability/settings", tags=["Traceability Admin"])
def update_traceability_settings(payload: SettingsPayload):
    previous = _settings()
    data = {**payload.model_dump(), "config_id": SETTINGS_ID, "updated_at": _now()}
    try:
        updated = db.update_document(database_id=db_id, collection_id=db_collection_id30, document_id=SETTINGS_ID, data=data)
        write_audit(action_type="Update", collection_name="Traceability Settings", performed_by_id=payload.updated_by, performed_by_role="admin", action_details="Updated the public traceability experience", previous_data=previous, new_data=data)
        return {"message": "Traceability settings updated", "settings": updated}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not update traceability settings: {error}") from error


@traceability_router.post("/traceability/batches/{batch_id}/publish", tags=["Traceability Admin"])
def publish_batch(batch_id: str, payload: PublishPayload):
    if payload.recall_status not in {"none", "advisory", "recalled"}:
        raise HTTPException(status_code=422, detail="recall_status must be none, advisory, or recalled")
    batch = _find_batch(batch_id)
    existing = next((item for item in _documents(db_collection_id31) if _clean(item.get("batch_id")) == batch_id), None)
    token = _clean((existing or {}).get("public_token")) or f"FS-{secrets.token_hex(6).upper()}"
    trace_id = _clean((existing or {}).get("trace_id") or (existing or {}).get("$id")) or ID.unique()
    now = _now()
    data = {
        "trace_id": trace_id,
        "batch_id": batch_id,
        "batch_number": _clean(batch.get("batch_no")),
        "public_token": token,
        "product_name": _clean(batch.get("plant_name")),
        "variety": _clean(batch.get("plant_variety")),
        "farm_name": _clean(batch.get("farm_name")),
        "farm_region": payload.farm_region.strip(),
        "packaging_label": payload.packaging_label.strip(),
        "quality_status": payload.quality_status.strip() or "Verified",
        "public_message": payload.public_message.strip(),
        "published": payload.published,
        "recall_status": payload.recall_status,
        "scan_count": int((existing or {}).get("scan_count") or 0),
        "published_at": now if payload.published else (existing or {}).get("published_at"),
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
        "created_by": payload.actor_id,
    }
    try:
        if existing:
            saved = db.update_document(database_id=db_id, collection_id=db_collection_id31, document_id=existing["$id"], data=data)
        else:
            saved = db.create_document(database_id=db_id, collection_id=db_collection_id31, document_id=trace_id, data=data)
        write_audit(action_type="Publish" if payload.published else "Unpublish", collection_name="Batch Traceability", performed_by_id=payload.actor_id, performed_by_role=payload.actor_role, action_details=f"{'Published' if payload.published else 'Unpublished'} batch {data['batch_number']}", previous_data=existing, new_data=data)
        config = _settings()
        return {"message": "Batch publication updated", "trace": saved, "public_url": f"{str(config.get('public_site_url') or '').rstrip('/')}/product/{token}"}
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Could not update batch publication: {error}") from error


@traceability_router.post("/traceability/promotions", tags=["Traceability Admin"])
def create_promotion(payload: PromotionPayload):
    if payload.status not in {"draft", "active", "paused", "expired"}:
        raise HTTPException(status_code=422, detail="Invalid promotion status")
    promotion_id = ID.unique()
    now = _now()
    data = {**payload.model_dump(exclude={"actor_id", "actor_role"}, exclude_none=True), "promotion_id": promotion_id, "impressions": 0, "clicks": 0, "created_by": payload.actor_id, "created_at": now, "updated_at": now}
    saved = db.create_document(database_id=db_id, collection_id=db_collection_id32, document_id=promotion_id, data=data)
    write_audit(action_type="Create", collection_name="Traceability Promotions", performed_by_id=payload.actor_id, performed_by_role=payload.actor_role, action_details=f"Created promotion {payload.title}", new_data=data)
    return {"message": "Promotion created", "promotion": saved}


@traceability_router.put("/traceability/promotions/{promotion_id}", tags=["Traceability Admin"])
def update_promotion(promotion_id: str, payload: PromotionPayload):
    try:
        previous = db.get_document(database_id=db_id, collection_id=db_collection_id32, document_id=promotion_id)
        data = {**payload.model_dump(exclude={"actor_id", "actor_role"}, exclude_none=True), "updated_at": _now()}
        saved = db.update_document(database_id=db_id, collection_id=db_collection_id32, document_id=promotion_id, data=data)
        write_audit(action_type="Update", collection_name="Traceability Promotions", performed_by_id=payload.actor_id, performed_by_role=payload.actor_role, action_details=f"Updated promotion {payload.title}", previous_data=previous, new_data=data)
        return {"message": "Promotion updated", "promotion": saved}
    except AppwriteException as error:
        raise HTTPException(status_code=404, detail="Promotion not found") from error


@traceability_router.delete("/traceability/promotions/{promotion_id}", tags=["Traceability Admin"])
def delete_promotion(promotion_id: str, actor_id: str = "system", actor_role: str = "superadmin"):
    try:
        previous = db.get_document(database_id=db_id, collection_id=db_collection_id32, document_id=promotion_id)
        db.delete_document(database_id=db_id, collection_id=db_collection_id32, document_id=promotion_id)
        write_audit(action_type="Delete", collection_name="Traceability Promotions", performed_by_id=actor_id, performed_by_role=actor_role, action_details=f"Deleted promotion {previous.get('title', '')}", previous_data=previous)
        return {"message": "Promotion deleted"}
    except AppwriteException as error:
        raise HTTPException(status_code=404, detail="Promotion not found") from error


@traceability_router.get("/public/traceability/config", tags=["Public Traceability"])
def public_traceability_config():
    return {"ok": True, "config": _public_config(_settings())}


def _lookup_response(request: Request, trace: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    config = _settings()
    if not config.get("lookup_enabled", True):
        raise HTTPException(status_code=503, detail={"code": "LOOKUP_DISABLED", "message": "Product verification is temporarily unavailable."})
    if config.get("analytics_enabled", True):
        _record_event(request, event_type="lookup_success", metadata=metadata, trace=trace)
        db.update_document(database_id=db_id, collection_id=db_collection_id31, document_id=trace["$id"], data={"scan_count": int(trace.get("scan_count") or 0) + 1, "updated_at": _now()})
    promotion = _active_promotion(trace, _clean(metadata.get("region"))) if config.get("promotions_enabled", True) else None
    return {"ok": True, "verified": trace.get("recall_status") != "recalled", "trace": _public_trace(trace, config), "promotion": promotion, "config": _public_config(config)}


@traceability_router.post("/public/traceability/lookup", tags=["Public Traceability"])
def public_lookup(request: Request, payload: LookupPayload):
    trace = _find_trace(batch_number=payload.batch_number)
    metadata = payload.model_dump()
    if trace is None:
        if _settings().get("analytics_enabled", True):
            _record_event(request, event_type="lookup_failed", metadata=metadata)
        raise HTTPException(status_code=404, detail={"code": "TRACE_NOT_FOUND", "message": "No published product was found for this batch number."})
    return _lookup_response(request, trace, metadata)


@traceability_router.get("/public/traceability/{public_token}", tags=["Public Traceability"])
def public_lookup_by_token(request: Request, public_token: str, session_id: str = "", country: str = "", region: str = "", city: str = "", device_type: str = "unknown", referrer: str = ""):
    trace = _find_trace(token=public_token)
    metadata = {"session_id": session_id, "country": country, "region": region, "city": city, "device_type": device_type, "referrer": referrer}
    if trace is None:
        raise HTTPException(status_code=404, detail={"code": "TRACE_NOT_FOUND", "message": "This product link is invalid or is not published."})
    return _lookup_response(request, trace, metadata)


@traceability_router.post("/public/traceability/events", status_code=status.HTTP_202_ACCEPTED, tags=["Public Traceability"])
def public_event(request: Request, payload: EventPayload):
    if payload.event_type not in {"page_view", "promotion_impression", "promotion_click"}:
        raise HTTPException(status_code=422, detail={"code": "INVALID_EVENT", "message": "Unsupported public event type."})
    if not _settings().get("analytics_enabled", True):
        return {"ok": True, "recorded": False}
    trace = _find_trace(token=payload.public_token) if payload.public_token else None
    event_id = _record_event(request, event_type=payload.event_type, metadata=payload.model_dump(), trace=trace)
    if payload.promotion_id and payload.event_type in {"promotion_impression", "promotion_click"}:
        try:
            promotion = db.get_document(database_id=db_id, collection_id=db_collection_id32, document_id=payload.promotion_id)
            counter = "impressions" if payload.event_type == "promotion_impression" else "clicks"
            db.update_document(
                database_id=db_id,
                collection_id=db_collection_id32,
                document_id=payload.promotion_id,
                data={counter: int(promotion.get(counter) or 0) + 1, "updated_at": _now()},
            )
        except AppwriteException:
            pass
    return {"ok": True, "event_id": event_id}
