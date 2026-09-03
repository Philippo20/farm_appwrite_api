import hashlib
import ipaddress
import json
import os
import secrets
import threading
import time
import urllib.parse
import urllib.request
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
    db_collection_id34,
    db_id,
)


traceability_router = APIRouter()
SETTINGS_ID = "global"
_GEO_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_GEO_CACHE_LOCK = threading.Lock()


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
        "maintenance_mode": False,
        "show_farm": True,
        "show_location": True,
        "show_dates": True,
        "show_quality": True,
        "show_journey": True,
        "analytics_enabled": True,
        "promotions_enabled": True,
        "feedback_enabled": True,
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


def _trusted_proxy_request(request: Request) -> bool:
    expected = os.getenv("TRACEABILITY_PROXY_SECRET", "").strip()
    supplied = _clean(request.headers.get("x-traceability-proxy-key"))
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def _normalize_ip(candidate: Any) -> str:
    value = _clean(candidate).split(",", 1)[0].strip().strip('"')
    if not value:
        return ""
    if value.startswith("[") and "]" in value:
        value = value[1:value.index("]")]
    elif value.count(":") == 1 and "." in value:
        value = value.split(":", 1)[0]
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ""


def _client_ip_details(request: Request) -> tuple[str, str]:
    configured_header = os.getenv(
        "TRACEABILITY_CLIENT_IP_HEADER", "do-connecting-ip"
    ).strip().lower()
    candidates: List[tuple[str, Any]] = []
    if _trusted_proxy_request(request):
        candidates.append(("trusted-proxy", request.headers.get("x-visitor-ip")))
    if configured_header:
        candidates.append((configured_header, request.headers.get(configured_header)))
    if configured_header != "do-connecting-ip":
        candidates.append(("do-connecting-ip", request.headers.get("do-connecting-ip")))
    candidates.extend(
        [
            ("x-real-ip", request.headers.get("x-real-ip")),
            ("socket", request.client.host if request.client else None),
        ]
    )
    for source, candidate in candidates:
        value = _normalize_ip(candidate)
        if not value:
            continue
        return value, source
    return "unknown", "unavailable"


def _client_ip(request: Request) -> str:
    return _client_ip_details(request)[0]


def _hash_ip(ip: str) -> str:
    salt = os.getenv("TRACEABILITY_IP_SALT") or "farmestates-traceability"
    return hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()


def _masked_ip(ip: str) -> str:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return "unknown"
    if address.version == 4:
        parts = str(address).split(".")
        return f"{parts[0]}.{parts[1]}.x.x"
    parts = address.exploded.split(":")
    return f"{parts[0]}:{parts[1]}:{parts[2]}::/48"


def _device_details(request: Request) -> Dict[str, str]:
    trusted_proxy = _trusted_proxy_request(request)
    forwarded_user_agent = _clean(request.headers.get("x-visitor-user-agent"))
    user_agent = (
        forwarded_user_agent
        if trusted_proxy and forwarded_user_agent
        else _clean(request.headers.get("user-agent"))
    )
    ua = user_agent.casefold()
    forwarded_mobile = _clean(request.headers.get("x-visitor-mobile"))
    mobile_hint = (
        forwarded_mobile
        if trusted_proxy and forwarded_mobile
        else _clean(request.headers.get("sec-ch-ua-mobile"))
    )
    forwarded_platform = _clean(request.headers.get("x-visitor-platform"))
    platform_hint = (
        forwarded_platform
        if trusted_proxy and forwarded_platform
        else _clean(request.headers.get("sec-ch-ua-platform"))
    ).strip('"')
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        device_type = "tablet"
    elif mobile_hint == "?1" or any(value in ua for value in ("mobile", "iphone", "android")):
        device_type = "mobile"
    else:
        device_type = "desktop"

    if "edg/" in ua:
        browser = "Microsoft Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "firefox/" in ua or "fxios/" in ua:
        browser = "Firefox"
    elif "chrome/" in ua or "crios/" in ua:
        browser = "Google Chrome"
    elif "safari/" in ua:
        browser = "Safari"
    else:
        browser = "Unknown"

    if platform_hint:
        operating_system = platform_hint
    elif "windows" in ua:
        operating_system = "Windows"
    elif "android" in ua:
        operating_system = "Android"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        operating_system = "iOS"
    elif "mac os" in ua or "macintosh" in ua:
        operating_system = "macOS"
    elif "linux" in ua:
        operating_system = "Linux"
    else:
        operating_system = "Unknown"
    return {
        "device_type": device_type,
        "browser": browser,
        "operating_system": operating_system,
        "user_agent": user_agent[:1000],
    }


def _geo_details(ip: str, request: Request) -> Dict[str, Any]:
    details: Dict[str, Any] = {
        "country": _clean(request.headers.get("cf-ipcountry")),
        "region": _clean(request.headers.get("cf-region")),
        "city": _clean(request.headers.get("cf-ipcity")),
        "latitude": 0.0,
        "longitude": 0.0,
        "timezone": _clean(request.headers.get("cf-timezone")),
        "isp": "",
    }
    try:
        address = ipaddress.ip_address(ip)
        if not address.is_global:
            return details
    except ValueError:
        return details

    now = time.monotonic()
    with _GEO_CACHE_LOCK:
        cached = _GEO_CACHE.get(ip)
        if cached and now - cached[0] < 3600:
            return {**details, **cached[1]}

    template = os.getenv("TRACEABILITY_GEOLOOKUP_URL", "https://ipwho.is/{ip}").strip()
    if not template:
        return details
    url = template.replace("{ip}", urllib.parse.quote(ip, safe=""))
    try:
        geo_request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "FarmEstates-Traceability/1.0"},
        )
        with urllib.request.urlopen(geo_request, timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("success") is False:
            return details
        connection = payload.get("connection") if isinstance(payload.get("connection"), dict) else {}
        timezone_data = payload.get("timezone") if isinstance(payload.get("timezone"), dict) else {}
        resolved = {
            "country": _clean(payload.get("country"))[:120],
            "region": _clean(payload.get("region"))[:160],
            "city": _clean(payload.get("city"))[:160],
            "latitude": float(payload.get("latitude") or 0.0),
            "longitude": float(payload.get("longitude") or 0.0),
            "timezone": _clean(timezone_data.get("id"))[:120],
            "isp": _clean(connection.get("isp"))[:225],
        }
        with _GEO_CACHE_LOCK:
            _GEO_CACHE[ip] = (now, resolved)
            if len(_GEO_CACHE) > 2000:
                oldest = min(_GEO_CACHE, key=lambda key: _GEO_CACHE[key][0])
                _GEO_CACHE.pop(oldest, None)
        return {**details, **resolved}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return details


def _visitor_context(request: Request) -> Dict[str, Any]:
    ip, ip_source = _client_ip_details(request)
    return {
        "ip_hash": _hash_ip(ip),
        "ip_masked": _masked_ip(ip),
        "ip_source": ip_source,
        **_geo_details(ip, request),
        **_device_details(request),
    }


def _record_event(
    request: Request,
    *,
    event_type: str,
    metadata: Dict[str, Any],
    trace: Optional[Dict[str, Any]] = None,
    visitor: Optional[Dict[str, Any]] = None,
) -> str:
    visitor = visitor or _visitor_context(request)
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
            "ip_hash": visitor["ip_hash"],
            "ip_masked": visitor["ip_masked"],
            "ip_source": visitor["ip_source"],
            "country": visitor["country"],
            "region": visitor["region"],
            "city": visitor["city"],
            "latitude": visitor["latitude"],
            "longitude": visitor["longitude"],
            "timezone": visitor["timezone"],
            "isp": visitor["isp"],
            "device_type": visitor["device_type"],
            "browser": visitor["browser"],
            "operating_system": visitor["operating_system"],
            "referrer": _clean(metadata.get("referrer"))[:1000],
            "user_agent": visitor["user_agent"],
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
        "maintenance_mode": config.get("maintenance_mode", False),
        "feedback_enabled": config.get("feedback_enabled", True),
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
    maintenance_mode: bool = False
    show_farm: bool = True
    show_location: bool = True
    show_dates: bool = True
    show_quality: bool = True
    show_journey: bool = True
    analytics_enabled: bool = True
    promotions_enabled: bool = True
    feedback_enabled: bool = True
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


class FeedbackPayload(BaseModel):
    feedback_type: str = "feedback"
    category: str = "other"
    rating: int = Field(default=0, ge=0, le=5)
    message: str = Field(min_length=5, max_length=4000)
    public_token: str = ""
    batch_number: str = ""
    contact_name: str = Field(default="", max_length=225)
    contact_email: str = Field(default="", max_length=320)
    consent_to_contact: bool = False
    session_id: str = Field(default="", max_length=225)


class FeedbackReviewPayload(BaseModel):
    status: str
    admin_notes: str = Field(default="", max_length=4000)
    actor_id: str = "system"
    actor_role: str = "admin"


@traceability_router.get("/traceability/overview", tags=["Traceability Admin"])
def traceability_overview():
    try:
        config = _settings()
        batches = _documents(db_collection_id5)
        traces = _documents(db_collection_id31)
        promotions = _documents(db_collection_id32)
        events = _documents(db_collection_id33)
        feedback = _documents(db_collection_id34)
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
            "open_reports": sum(1 for item in feedback if item.get("status") in {"new", "reviewing"}),
        }
        return {
            "settings": config,
            "metrics": metrics,
            "batches": product_rows,
            "promotions": promotions,
            "events": sorted(events, key=lambda item: str(item.get("occurred_at") or ""), reverse=True)[:100],
            "feedback": sorted(feedback, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:500],
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


@traceability_router.put("/traceability/feedback/{feedback_id}", tags=["Traceability Admin"])
def review_feedback(feedback_id: str, payload: FeedbackReviewPayload):
    if payload.status not in {"new", "reviewing", "resolved", "closed"}:
        raise HTTPException(status_code=422, detail="Invalid feedback status")
    try:
        previous = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id34,
            document_id=feedback_id,
        )
        data = {
            "status": payload.status,
            "admin_notes": payload.admin_notes.strip(),
            "updated_at": _now(),
        }
        saved = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id34,
            document_id=feedback_id,
            data=data,
        )
        write_audit(
            action_type="Update",
            collection_name="Traceability Feedback",
            performed_by_id=payload.actor_id,
            performed_by_role=payload.actor_role,
            action_details=f"Marked traceability {previous.get('feedback_type', 'feedback')} as {payload.status}",
            previous_data=previous,
            new_data=data,
        )
        return {"message": "Feedback review updated", "feedback": saved}
    except AppwriteException as error:
        raise HTTPException(status_code=404, detail="Feedback record not found") from error


@traceability_router.get("/public/traceability/config", tags=["Public Traceability"])
def public_traceability_config():
    return {"ok": True, "config": _public_config(_settings())}


@traceability_router.post(
    "/public/traceability/feedback",
    status_code=status.HTTP_201_CREATED,
    tags=["Public Traceability"],
)
def submit_public_feedback(request: Request, payload: FeedbackPayload):
    config = _settings()
    if not config.get("feedback_enabled", True):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "FEEDBACK_DISABLED",
                "message": "Feedback submissions are temporarily unavailable.",
            },
        )
    if payload.feedback_type not in {"feedback", "issue"}:
        raise HTTPException(status_code=422, detail="feedback_type must be feedback or issue")
    if payload.category not in {"product_quality", "packaging", "delivery", "traceability", "other"}:
        raise HTTPException(status_code=422, detail="Invalid feedback category")
    if payload.feedback_type == "feedback" and payload.rating not in {1, 2, 3, 4, 5}:
        raise HTTPException(status_code=422, detail="A rating from 1 to 5 is required for feedback")
    if payload.consent_to_contact and not payload.contact_email.strip():
        raise HTTPException(status_code=422, detail="Contact email is required when follow-up consent is enabled")
    if payload.contact_email and ("@" not in payload.contact_email or "." not in payload.contact_email.rsplit("@", 1)[-1]):
        raise HTTPException(status_code=422, detail="Enter a valid contact email")

    trace = _find_trace(batch_number=payload.batch_number, token=payload.public_token)
    visitor = _visitor_context(request)
    feedback_id = ID.unique()
    now = _now()
    data = {
        "feedback_id": feedback_id,
        "trace_id": _clean((trace or {}).get("trace_id")),
        "batch_number": _clean(payload.batch_number or (trace or {}).get("batch_number")),
        "public_token": _clean(payload.public_token or (trace or {}).get("public_token")),
        "feedback_type": payload.feedback_type,
        "category": payload.category,
        "rating": payload.rating if payload.feedback_type == "feedback" else 0,
        "message": payload.message.strip(),
        "contact_name": payload.contact_name.strip(),
        "contact_email": payload.contact_email.strip().lower(),
        "consent_to_contact": payload.consent_to_contact,
        "anonymous_session": payload.session_id.strip(),
        "ip_hash": visitor["ip_hash"],
        "ip_masked": visitor["ip_masked"],
        "ip_source": visitor["ip_source"],
        "country": visitor["country"],
        "region": visitor["region"],
        "city": visitor["city"],
        "latitude": visitor["latitude"],
        "longitude": visitor["longitude"],
        "timezone": visitor["timezone"],
        "isp": visitor["isp"],
        "device_type": visitor["device_type"],
        "browser": visitor["browser"],
        "operating_system": visitor["operating_system"],
        "status": "new",
        "admin_notes": "",
        "created_at": now,
        "updated_at": now,
    }
    db.create_document(
        database_id=db_id,
        collection_id=db_collection_id34,
        document_id=feedback_id,
        data=data,
    )
    return {
        "ok": True,
        "feedback_id": feedback_id,
        "message": "Thank you. Your feedback has been received.",
    }


def _available_public_config() -> Dict[str, Any]:
    config = _settings()
    if config.get("maintenance_mode", False):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "TRACEABILITY_MAINTENANCE",
                "message": "Product verification is temporarily unavailable while scheduled maintenance is in progress.",
            },
        )
    if not config.get("lookup_enabled", True):
        raise HTTPException(status_code=503, detail={"code": "LOOKUP_DISABLED", "message": "Product verification is temporarily unavailable."})
    return config


def _lookup_response(request: Request, trace: Dict[str, Any], metadata: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    visitor = _visitor_context(request)
    if config.get("analytics_enabled", True):
        _record_event(request, event_type="lookup_success", metadata=metadata, trace=trace, visitor=visitor)
        db.update_document(database_id=db_id, collection_id=db_collection_id31, document_id=trace["$id"], data={"scan_count": int(trace.get("scan_count") or 0) + 1, "updated_at": _now()})
    promotion = _active_promotion(trace, visitor["region"]) if config.get("promotions_enabled", True) else None
    return {"ok": True, "verified": trace.get("recall_status") != "recalled", "trace": _public_trace(trace, config), "promotion": promotion, "config": _public_config(config)}


@traceability_router.post("/public/traceability/lookup", tags=["Public Traceability"])
def public_lookup(request: Request, payload: LookupPayload):
    config = _available_public_config()
    trace = _find_trace(batch_number=payload.batch_number)
    metadata = payload.model_dump()
    if trace is None:
        if config.get("analytics_enabled", True):
            _record_event(request, event_type="lookup_failed", metadata=metadata)
        raise HTTPException(status_code=404, detail={"code": "TRACE_NOT_FOUND", "message": "No published product was found for this batch number."})
    return _lookup_response(request, trace, metadata, config)


@traceability_router.get("/public/traceability/{public_token}", tags=["Public Traceability"])
def public_lookup_by_token(request: Request, public_token: str, session_id: str = "", country: str = "", region: str = "", city: str = "", device_type: str = "unknown", referrer: str = ""):
    config = _available_public_config()
    trace = _find_trace(token=public_token)
    metadata = {"session_id": session_id, "country": country, "region": region, "city": city, "device_type": device_type, "referrer": referrer}
    if trace is None:
        raise HTTPException(status_code=404, detail={"code": "TRACE_NOT_FOUND", "message": "This product link is invalid or is not published."})
    return _lookup_response(request, trace, metadata, config)


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
