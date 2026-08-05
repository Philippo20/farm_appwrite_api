import secrets
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, status
from appwrite.exception import AppwriteException

from main import db_id, db_collection_id18
from db import db
from audit_utils import write_audit


collection18_router = APIRouter(tags=["System Config"])

CONFIG_DOCUMENT_ID = "global"

DEFAULT_CONFIG: Dict[str, Any] = {
    "email_notifications": True,
    "sms_notifications": False,
    "maintenance_mode": False,
    "auto_backup": True,
    "two_factor_auth": True,
    "session_timeout": 30,
    "session_idle_warning_minutes": 5,
    "max_concurrent_sessions": 3,
    "force_logout_on_password_change": True,
    "password_min_length": 8,
    "max_upload_size": 50,
    "api_base_url": "https://api.farmestates.com",
    "webhook_url": "https://hooks.farmestates.com",
    "api_rate_limit": 1000,
    "sensor_ingest_api_key": "",
    "currency_code": "GHS",
    "currency_symbol": "GHS",
    "google_maps_enabled": False,
    "google_maps_api_key": "",
    "google_maps_default_lat": 5.6037,
    "google_maps_default_lng": -0.1870,
    "google_maps_default_zoom": 10,
    "fulfillment_push_alerts": True,
    "fulfillment_dock_escalations": True,
    "fulfillment_auto_reorder_drafts": False,
    "updated_by": "system",
}


def _require_collection():
    if not db_collection_id18:
        raise HTTPException(
            status_code=500,
            detail="APPWRITE_COLLECTION_ID18 is not configured for System Config",
        )


def _normalize_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**DEFAULT_CONFIG, **payload}

    session_timeout = int(merged["session_timeout"])
    session_idle_warning_minutes = int(merged["session_idle_warning_minutes"])
    max_concurrent_sessions = int(merged["max_concurrent_sessions"])
    password_min_length = int(merged["password_min_length"])
    max_upload_size = int(merged["max_upload_size"])
    api_rate_limit = int(merged["api_rate_limit"])
    google_zoom = int(merged["google_maps_default_zoom"])
    google_lat = float(merged["google_maps_default_lat"])
    google_lng = float(merged["google_maps_default_lng"])

    if not 5 <= session_timeout <= 1440:
        raise HTTPException(400, "Session timeout must be between 5 and 1440 minutes")
    if not 1 <= session_idle_warning_minutes <= 120:
        raise HTTPException(400, "Session idle warning must be between 1 and 120 minutes")
    if session_idle_warning_minutes >= session_timeout:
        raise HTTPException(400, "Session idle warning must be lower than the session timeout")
    if not 1 <= max_concurrent_sessions <= 20:
        raise HTTPException(400, "Max concurrent sessions must be between 1 and 20")
    if not 6 <= password_min_length <= 32:
        raise HTTPException(400, "Password minimum length must be between 6 and 32 characters")
    if not 1 <= max_upload_size <= 500:
        raise HTTPException(400, "Max upload size must be between 1 and 500 MB")
    if not 10 <= api_rate_limit <= 10000:
        raise HTTPException(400, "API rate limit must be between 10 and 10000 requests per minute")
    if merged["currency_code"] not in ["GHS", "USD", "EUR", "GBP"]:
        raise HTTPException(400, "Currency must be one of GHS, USD, EUR, or GBP")
    if not -90 <= google_lat <= 90:
        raise HTTPException(400, "Google Maps latitude must be between -90 and 90")
    if not -180 <= google_lng <= 180:
        raise HTTPException(400, "Google Maps longitude must be between -180 and 180")
    if not 1 <= google_zoom <= 22:
        raise HTTPException(400, "Google Maps zoom must be between 1 and 22")

    return {
        "email_notifications": bool(merged["email_notifications"]),
        "sms_notifications": bool(merged["sms_notifications"]),
        "maintenance_mode": bool(merged["maintenance_mode"]),
        "auto_backup": bool(merged["auto_backup"]),
        "two_factor_auth": bool(merged["two_factor_auth"]),
        "session_timeout": session_timeout,
        "session_idle_warning_minutes": session_idle_warning_minutes,
        "max_concurrent_sessions": max_concurrent_sessions,
        "force_logout_on_password_change": bool(merged["force_logout_on_password_change"]),
        "password_min_length": password_min_length,
        "max_upload_size": max_upload_size,
        "api_base_url": str(merged["api_base_url"]).strip(),
        "webhook_url": str(merged["webhook_url"]).strip(),
        "api_rate_limit": api_rate_limit,
        "sensor_ingest_api_key": str(merged.get("sensor_ingest_api_key") or "").strip(),
        "currency_code": str(merged["currency_code"]).strip(),
        "currency_symbol": str(merged["currency_symbol"]).strip() or "GHS",
        "google_maps_enabled": bool(merged["google_maps_enabled"]),
        "google_maps_api_key": str(merged["google_maps_api_key"]).strip(),
        "google_maps_default_lat": google_lat,
        "google_maps_default_lng": google_lng,
        "google_maps_default_zoom": google_zoom,
        "fulfillment_push_alerts": bool(merged["fulfillment_push_alerts"]),
        "fulfillment_dock_escalations": bool(merged["fulfillment_dock_escalations"]),
        "fulfillment_auto_reorder_drafts": bool(merged["fulfillment_auto_reorder_drafts"]),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": str(merged.get("updated_by") or "system").strip(),
    }


def _get_or_create_config() -> Dict[str, Any]:
    _require_collection()
    try:
        return db.get_document(
            database_id=db_id,
            collection_id=db_collection_id18,
            document_id=CONFIG_DOCUMENT_ID,
        )
    except AppwriteException as error:
        if error.code != 404:
            raise
        data = _normalize_config(DEFAULT_CONFIG)
        return db.create_document(
            database_id=db_id,
            collection_id=db_collection_id18,
            document_id=CONFIG_DOCUMENT_ID,
            data=data,
        )


@collection18_router.get("/system-config")
def get_system_config():
    try:
        return {"config": _get_or_create_config()}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection18_router.put("/system-config")
def update_system_config(payload: Dict[str, Any] = Body(...)):
    try:
        previous_config = _get_or_create_config()
        update_data = _normalize_config({**previous_config, **payload})
        updated_config = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id18,
            document_id=CONFIG_DOCUMENT_ID,
            data=update_data,
        )
        write_audit(
            action_type="Update",
            collection_name="System Config",
            performed_by_id=update_data.get("updated_by", "system"),
            performed_by_role="superadmin",
            action_details="Updated global system configuration",
            previous_data=previous_config,
            new_data=update_data,
        )
        return {"message": "System configuration updated successfully", "config": updated_config}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))


@collection18_router.post("/system-config/sensor-api-key")
def generate_sensor_ingest_api_key(payload: Dict[str, Any] = Body(default={})):
    try:
        previous_config = _get_or_create_config()
        updated_by = str(payload.get("updated_by") or "system").strip()
        generated_key = f"fs_sensor_{secrets.token_urlsafe(32)}"
        update_data = _normalize_config(
            {
                **previous_config,
                "sensor_ingest_api_key": generated_key,
                "updated_by": updated_by,
            }
        )
        updated_config = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id18,
            document_id=CONFIG_DOCUMENT_ID,
            data=update_data,
        )
        write_audit(
            action_type="Update",
            collection_name="System Config",
            performed_by_id=updated_by,
            performed_by_role="superadmin",
            action_details="Generated a new sensor ingestion API key",
            previous_data={
                **previous_config,
                "sensor_ingest_api_key": "***configured***"
                if previous_config.get("sensor_ingest_api_key")
                else "",
            },
            new_data={**update_data, "sensor_ingest_api_key": "***generated***"},
        )
        return {
            "message": "Sensor ingestion API key generated successfully",
            "config": updated_config,
            "sensor_ingest_api_key": generated_key,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))
