from datetime import datetime, timezone
from typing import Any

from appwrite.id import ID
from fastapi import APIRouter, HTTPException

from audit_utils import write_audit
from db import db
from main import db_collection_id27, db_id

collection27_router = APIRouter(tags=["Caretaker Settings"])
BOOL_FIELDS = {
    "task_reminders", "anomaly_alerts", "weather_warnings", "chat_notifications",
    "email_summaries", "sound_alerts", "offline_mode", "auto_sync_records",
    "compact_cards", "biometric_lock",
}
STRING_FIELDS = {
    "shift_start", "reminder_lead_time", "default_landing_page", "theme_mode",
}
DEFAULTS = {
    "task_reminders": True, "anomaly_alerts": True, "weather_warnings": True,
    "chat_notifications": True, "email_summaries": False, "sound_alerts": True,
    "offline_mode": True, "auto_sync_records": True, "compact_cards": False,
    "biometric_lock": False, "shift_start": "06:00 AM",
    "reminder_lead_time": "30 minutes", "default_landing_page": "Dashboard",
    "theme_mode": "system",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get(user_id: str):
    documents = db.list_documents(
        database_id=db_id, collection_id=db_collection_id27
    ).get("documents", [])
    return next((item for item in documents if item.get("user_id") == user_id), None)


def _settings(document: dict[str, Any] | None, user_id: str):
    values = {**DEFAULTS, "user_id": user_id}
    if document:
        values.update({key: document[key] for key in DEFAULTS if key in document})
        values["$id"] = document.get("$id", "")
        values["updated_at"] = document.get("updated_at", "")
    return values


@collection27_router.get("/caretaker-settings")
def get_caretaker_settings(user_id: str):
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        return {"settings": _settings(_get(user_id), user_id)}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection27_router.put("/caretaker-settings/{user_id}")
def update_caretaker_settings(user_id: str, payload: dict[str, Any]):
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    unknown = set(payload) - (BOOL_FIELDS | STRING_FIELDS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unsupported setting(s): {', '.join(sorted(unknown))}")
    try:
        previous_document = _get(user_id)
        update_data = {"user_id": user_id, "updated_at": _now()}
        for key in BOOL_FIELDS:
            if key in payload:
                update_data[key] = bool(payload[key])
        for key in STRING_FIELDS:
            if key in payload:
                update_data[key] = str(payload[key])
        if previous_document:
            updated = db.update_document(
                database_id=db_id, collection_id=db_collection_id27,
                document_id=previous_document["$id"], data=update_data,
            )
        else:
            updated = db.create_document(
                database_id=db_id, collection_id=db_collection_id27,
                document_id=ID.unique(), data={**DEFAULTS, **update_data},
            )
        write_audit(
            action_type="Update", collection_name="Caretaker Settings",
            performed_by_id=user_id, performed_by_role="caretaker",
            action_details="Updated caretaker preferences",
            previous_data=previous_document or {}, new_data=update_data,
        )
        return {"message": "Caretaker settings updated successfully", "settings": updated}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
