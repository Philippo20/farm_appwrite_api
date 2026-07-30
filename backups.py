import os
import io
import json
import tempfile
import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, APIRouter, Body
from pydantic import BaseModel
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.storage import Storage
from appwrite.id import ID
from appwrite.input_file import InputFile
from appwrite.query import Query
from audit_utils import write_audit

# Optional scheduler for auto backups
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

APPWRITE_ENDPOINT = os.getenv("APPWRITE_ENDPOINT")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.getenv("APPWRITE_API_KEY")
APPWRITE_DB_ID = os.getenv("APPWRITE_DB_ID") or os.getenv("APPWRITE_DATABASE_ID")
BACKUPS_COLLECTION_ID = (
    os.getenv("BACKUPS_COLLECTION_ID")
    or os.getenv("APPWRITE_COLLECTION_ID19")
    or "backups"
)
APPWRITE_BUCKET_ID = os.getenv("APPWRITE_BUCKET_ID", "backups_bucket_id")

if not (APPWRITE_ENDPOINT and APPWRITE_PROJECT_ID and APPWRITE_API_KEY):
    raise RuntimeError("Set APPWRITE_ENDPOINT, APPWRITE_PROJECT_ID and APPWRITE_API_KEY in .env")

def get_server_client():
    client = Client()
    client.set_endpoint(APPWRITE_ENDPOINT)
    client.set_project(APPWRITE_PROJECT_ID)
    client.set_key(APPWRITE_API_KEY)
    client.set_self_signed(
        os.getenv("APPWRITE_SELF_SIGNED", "false").strip().lower() == "true"
    )
    return client

client = get_server_client()
db = Databases(client)
storage = Storage(client)


backups_router = APIRouter(tags=["Backups & Restore"])


# Scheduler for auto backups (runs in-process; in production use external scheduler)
scheduler = BackgroundScheduler()
scheduler.start()

# ------------- Helpers -------------
def list_collections():
    """Return a list of collection ids (and optionally names) in the project."""
    # Databases.list_collections exists in some SDK versions; fallback: list by database
    # We assume one database for simplicity: use default DB id from env or fetch list
    # Here we call databases.list_collections for DATABASE_ID from env if provided
    db_id = APPWRITE_DB_ID
    if not db_id:
        raise RuntimeError("APPWRITE_DB_ID is not configured")
    collections = db.list_collections(database_id=db_id).get("collections", [])
    return db_id, collections

def export_collection_to_json(database_id: str, collection_id: str) -> bytes:
    """Export all rows of a collection as JSON bytes."""
    # Pagination loop: Appwrite list_documents / list_rows supports limit/offset
    limit = 100
    offset = 0
    rows = []
    while True:
        resp = db.list_documents(
            database_id=database_id,
            collection_id=collection_id,
            queries=[Query.limit(limit), Query.offset(offset)]
        )
        docs = resp.get("documents", []) or resp.get("rows", [])
        if not docs:
            break
        rows.extend(docs)
        if len(docs) < limit:
            break
        offset += limit
    return json.dumps(rows, default=str, ensure_ascii=False).encode("utf-8")

def upload_backup_file(content: bytes, filename: str, content_type: str = "application/json"):
    """Upload bytes to Appwrite storage and return file record."""
    result = storage.create_file(
        bucket_id=APPWRITE_BUCKET_ID,
        file_id=ID.unique(),
        file=InputFile.from_bytes(content, filename=filename)
    )
    return result

def record_backup_metadata(file_rec: dict, collections_exported: List[str], notes: Optional[str] = None):
    """Create a row in backups collection to track metadata."""
    size_bytes = int(file_rec.get("sizeOriginal", 0) or file_rec.get("size", 0) or 0)
    data = {
        "file_id": file_rec["$id"],
        "file_name": file_rec.get("name") or file_rec.get("filename"),
        "size_bytes": size_bytes,
        "collections": collections_exported,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "notes": notes or "",
        "backup_type": "Automated" if notes == "auto-scheduled" else "Manual",
        "status": "Verified",
        "scope": "global",
        "farm": "Global Platform",
        "retention_days": 90,
    }
    # store in backups collection (DATABASE_ID required)
    db_id = APPWRITE_DB_ID
    if not db_id:
        raise RuntimeError("APPWRITE_DB_ID is not configured")
    rec = db.create_document(database_id=db_id, collection_id=BACKUPS_COLLECTION_ID, document_id=ID.unique(), data=data)
    return rec

def build_backup_filename(prefix="backup"):
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{ts}.json"

# ------------- API models -------------
class BackupCreateResponse(BaseModel):
    backup_id: str
    file_id: str
    file_name: str
    size_bytes: int

class BackupItem(BaseModel):
    id: str
    file_id: str
    file_name: str
    size_bytes: int
    collections: List[str]
    created_at: str
    notes: Optional[str]
    backup_type: Optional[str] = "Manual"
    status: Optional[str] = "Verified"
    scope: Optional[str] = "global"
    farm: Optional[str] = "Global Platform"
    retention_days: Optional[int] = 90


@backups_router.post("/backups/create", response_model=BackupCreateResponse)
def create_backup(background: BackgroundTasks, notes: Optional[str] = None):
    """
    Create a backup of all collections and upload to Appwrite storage.
    This runs the export and upload synchronously, but could also be scheduled.
    """
    try:
        db_id, collections = list_collections()
        if not collections:
            raise HTTPException(400, "No collections found to backup")
        exported_collections = []
        combined = {}
        for col in collections:
            col_id = col["$id"]
            col_name = col.get("name", col_id)
            exported_collections.append(col_name)
            data_bytes = export_collection_to_json(db_id, col_id)
            # Store each collection under a key
            combined[col_name] = json.loads(data_bytes.decode("utf-8"))

        # Create single file with dict of collections
        file_bytes = json.dumps(combined, default=str, ensure_ascii=False).encode("utf-8")
        filename = build_backup_filename("farmestates-backup")
        file_rec = upload_backup_file(file_bytes, filename)

        # record metadata
        rec = record_backup_metadata(file_rec, exported_collections, notes=notes)
        write_audit(
            action_type="Create",
            collection_name="Backups",
            action_details=f"Created backup {file_rec.get('name') or file_rec.get('filename')}",
            new_data={
                "backup_id": rec["$id"],
                "file_id": file_rec["$id"],
                "collections": exported_collections,
                "notes": notes or "",
            }
        )
        return BackupCreateResponse(
            backup_id=rec["$id"],
            file_id=file_rec["$id"],
            file_name=file_rec.get("name") or file_rec.get("filename"),
            size_bytes=int(file_rec.get("sizeOriginal", 0) or file_rec.get("size", 0) or 0)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@backups_router.get("/backups", response_model=List[BackupItem])
def list_backups(limit: int = 50, offset: int = 0):
    """List backup metadata rows from backups collection."""
    try:
        db_id = APPWRITE_DB_ID
        if not db_id:
            raise RuntimeError("APPWRITE_DB_ID is not configured")
        res = db.list_documents(
            database_id=db_id,
            collection_id=BACKUPS_COLLECTION_ID,
            queries=[Query.limit(limit), Query.offset(offset)]
        )
        docs = res.get("documents", []) or res.get("rows", [])
        items = []
        for d in docs:
            items.append(BackupItem(
                id=d["$id"],
                file_id=d["file_id"],
                file_name=d["file_name"],
                size_bytes=int(d.get("size_bytes", 0)),
                collections=d.get("collections", []),
                created_at=d.get("created_at"),
                notes=d.get("notes", ""),
                backup_type=d.get("backup_type", "Manual"),
                status=d.get("status", "Verified"),
                scope=d.get("scope", "global"),
                farm=d.get("farm", "Global Platform"),
                retention_days=int(d.get("retention_days", 90) or 90)
            ))
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@backups_router.get("/backups/{backup_id}/download")
def download_backup(backup_id: str):
    """Return a download URL or redirect for stored backup file."""
    try:
        db_id = APPWRITE_DB_ID
        if not db_id:
            raise RuntimeError("APPWRITE_DB_ID is not configured")
        rec = db.get_document(database_id=db_id, collection_id=BACKUPS_COLLECTION_ID, document_id=backup_id)
        file_id = rec["file_id"]
        download_url = (
            f"{APPWRITE_ENDPOINT}/storage/buckets/{APPWRITE_BUCKET_ID}"
            f"/files/{file_id}/download?project={APPWRITE_PROJECT_ID}"
        )
        return {"download_url": download_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@backups_router.delete("/backups/{backup_id}")
def delete_backup(backup_id: str):
    """Delete a backup file and its metadata record."""
    try:
        db_id = APPWRITE_DB_ID
        if not db_id:
            raise RuntimeError("APPWRITE_DB_ID is not configured")

        previous_backup = db.get_document(
            database_id=db_id,
            collection_id=BACKUPS_COLLECTION_ID,
            document_id=backup_id
        )
        file_id = previous_backup.get("file_id")
        if file_id:
            try:
                storage.delete_file(bucket_id=APPWRITE_BUCKET_ID, file_id=file_id)
            except Exception:
                # Keep deleting metadata even if the storage file is already missing.
                pass

        db.delete_document(
            database_id=db_id,
            collection_id=BACKUPS_COLLECTION_ID,
            document_id=backup_id
        )
        write_audit(
            action_type="Delete",
            collection_name="Backups",
            action_details=f"Deleted backup {previous_backup.get('file_name', backup_id)}",
            previous_data=previous_backup
        )
        return {"message": "Backup deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@backups_router.patch("/backups/{backup_id}/retention")
def update_backup_retention(backup_id: str, payload: dict = Body(...)):
    """Update retention days for a backup metadata record."""
    try:
        retention_days = int(payload.get("retention_days", 90))
        if retention_days < 1 or retention_days > 3650:
            raise HTTPException(400, "Retention days must be between 1 and 3650")

        db_id = APPWRITE_DB_ID
        if not db_id:
            raise RuntimeError("APPWRITE_DB_ID is not configured")

        previous_backup = db.get_document(
            database_id=db_id,
            collection_id=BACKUPS_COLLECTION_ID,
            document_id=backup_id
        )
        updated_backup = db.update_document(
            database_id=db_id,
            collection_id=BACKUPS_COLLECTION_ID,
            document_id=backup_id,
            data={"retention_days": retention_days}
        )
        write_audit(
            action_type="Update",
            collection_name="Backups",
            action_details=f"Updated backup retention to {retention_days} days",
            previous_data=previous_backup,
            new_data={"retention_days": retention_days}
        )
        return {"message": "Backup retention updated successfully", "backup": updated_backup}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@backups_router.post("/backups/restore")
def restore_backup(file: UploadFile = File(...), replace_collections: bool = True):
    """
    Restore from an uploaded backup file (JSON). If replace_collections=True it will delete
    existing documents and re-insert documents from the backup.
    """
    try:
        content = file.file.read()
        payload = json.loads(content.decode("utf-8"))
        # payload expected: { "<collectionName>": [ {doc}, ... ], ... }
        db_id, collections_meta = list_collections()
        # Build lookup: name -> id
        name_to_id = {c.get("name") or c["$id"]: c["$id"] for c in collections_meta}

        for col_name, docs in payload.items():
            if col_name not in name_to_id:
                # skip or create collection — for safety we error
                raise HTTPException(400, f"Collection {col_name} not found in project")

            col_id = name_to_id[col_name]
            if replace_collections:
                # delete all existing documents in collection (use list_documents -> delete loop)
                limit = 100
                offset = 0
                while True:
                    resp = db.list_documents(
                        database_id=db_id,
                        collection_id=col_id,
                        queries=[Query.limit(limit), Query.offset(offset)]
                    )
                    existing = resp.get("documents", []) or resp.get("rows", [])
                    if not existing:
                        break
                    for ex in existing:
                        db.delete_document(database_id=db_id, collection_id=col_id, document_id=ex["$id"])
                    if len(existing) < limit:
                        break
                    offset += limit

            # Insert docs from backup
            for doc in docs:
                # Remove system fields if present
                doc_copy = {k: v for k, v in doc.items() if not k.startswith("$")}
                # create_document requires unique id param; we let Appwrite create new id
                db.create_document(database_id=db_id, collection_id=col_id, document_id=ID.unique(), data=doc_copy)

        write_audit(
            action_type="Update",
            collection_name="Backups",
            action_details=f"Restored backup file {file.filename}",
            new_data={
                "file_name": file.filename,
                "replace_collections": replace_collections,
                "collections": list(payload.keys()),
            }
        )
        return {"message": "Restore completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@backups_router.get("/backups/stats")
def backup_stats():
    """Return total backups, total size, last backup date."""
    try:
        db_id = APPWRITE_DB_ID
        if not db_id:
            raise RuntimeError("APPWRITE_DB_ID is not configured")
        res = db.list_documents(
            database_id=db_id,
            collection_id=BACKUPS_COLLECTION_ID,
            queries=[Query.limit(1000)]
        )
        docs = res.get("documents", []) or res.get("rows", [])
        total = len(docs)
        total_size = sum(int(d.get("size_bytes", 0) or 0) for d in docs)
        last = max((d.get("created_at") for d in docs), default=None)
        return {"total_backups": total, "total_size_bytes": total_size, "last_backup_at": last}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------- Auto-backup toggle and scheduler -------------
AUTO_BACKUP_ENABLED_KEY = "AUTO_BACKUP_ENABLED"

def job_create_auto_backup():
    try:
        # call create_backup but directly (no background tasks)
        create_backup(background=BackgroundTasks(), notes="auto-scheduled")
    except Exception as e:
        print("Auto-backup failed:", e)

@backups_router.post("/backups/auto/toggle")
def toggle_auto_backup(enable: bool):
    """
    Toggle auto backups. For demo we store state in environment file or backups collection.
    Production: use a persisted config store.
    """
    # Simple approach: store in backups collection a single row with key
    try:
        db_id = APPWRITE_DB_ID
        if not db_id:
            raise RuntimeError("APPWRITE_DB_ID is not configured")
        # For simplicity, store as document with id AUTO_BACKUP_ENABLED_KEY (create or update)
        try:
            conf = db.get_document(database_id=db_id, collection_id=BACKUPS_COLLECTION_ID, document_id=AUTO_BACKUP_ENABLED_KEY)
            db.update_document(database_id=db_id, collection_id=BACKUPS_COLLECTION_ID, document_id=AUTO_BACKUP_ENABLED_KEY, data={"auto_enabled": enable})
        except Exception:
            # create config document
            conf = None
            db.create_document(database_id=db_id, collection_id=BACKUPS_COLLECTION_ID, document_id=AUTO_BACKUP_ENABLED_KEY, data={"auto_enabled": enable})

        # Scheduler control: simple cron - every day at 02:00 UTC
        if enable:
            # add job if not exists
            if not scheduler.get_job("auto_backup_job"):
                scheduler.add_job(job_create_auto_backup, "cron", hour=2, minute=0, id="auto_backup_job")
        else:
            if scheduler.get_job("auto_backup_job"):
                scheduler.remove_job("auto_backup_job")
        write_audit(
            action_type="Update",
            collection_name="System Config",
            action_details=f"Set auto backup to {enable}",
            previous_data=conf,
            new_data={"auto_enabled": enable}
        )
        return {"auto_backup": enable}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
