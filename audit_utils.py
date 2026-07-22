import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from appwrite.id import ID

from db import db
from main import db_collection_id6, db_id


def _clean(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            key: _clean(item)
            for key, item in value.items()
            if not str(key).startswith("$") and key != "password"
        }
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _short_text(value: Any, limit: int = 225) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(_clean(value), default=str, separators=(",", ":"))
    return value if len(value) <= limit else f"{value[: limit - 3]}..."


def write_audit(
    *,
    action_type: str,
    collection_name: str,
    action_details: str,
    status: str = "Success",
    performed_by_id: str = "system",
    performed_by_role: str = "superadmin",
    ip_address: str = "-",
    previous_data: Any = None,
    new_data: Any = None,
) -> None:
    try:
        db.create_document(
            database_id=db_id,
            collection_id=db_collection_id6,
            document_id=ID.unique(),
            data={
                "audit_id": ID.unique(),
                "action_type": action_type,
                "collection_name": collection_name,
                "performed_by_id": _short_text(performed_by_id),
                "performed_by_role": performed_by_role,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action_details": _short_text(action_details),
                "ip_address": _short_text(ip_address),
                "status": status,
                "previous_data": _short_text(previous_data),
                "new_data": _short_text(new_data),
            },
        )
    except Exception as error:
        print(f"Audit write failed: {error}")
