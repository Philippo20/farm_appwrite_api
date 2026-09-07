"""Authenticated, persistent direct messages for the farm team."""
import hashlib
import os
from datetime import datetime, timezone

from appwrite.exception import AppwriteException
from appwrite.query import Query
from appwrite.services.account import Account
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from auth import get_user_client_from_jwt
from db import db
from main import db_id, db_collection_id1

messaging_router = APIRouter(prefix="/messages", tags=["Messages"])
MESSAGES = os.getenv("APPWRITE_MESSAGES_COLLECTION_ID", "team_messages")


def _all(collection, queries):
    documents = []
    offset = 0
    while True:
        page = db.list_documents(database_id=db_id, collection_id=collection,
                                 queries=[*queries, Query.limit(100), Query.offset(offset)])
        rows = page.get("documents", [])
        documents.extend(rows)
        if len(rows) < 100:
            return documents
        offset += len(rows)


def current_member(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please sign in to use messages.")
    try:
        account = Account(get_user_client_from_jwt(authorization[7:])).get()
    except Exception as error:
        raise HTTPException(401, "Your session has expired. Please sign in again.") from error
    members = _all(db_collection_id1, [Query.equal("email", account["email"])])
    member = next((item for item in members if item.get("status", "Active").lower() == "active"), None)
    if member is None:
        raise HTTPException(403, "Your account is not active.")
    return member


def _conversation(actor, peer):
    return hashlib.sha256("|".join(sorted([actor, peer])).encode()).hexdigest()[:36]


def _peer(peer_id, actor):
    if peer_id == actor["$id"]:
        raise HTTPException(400, "Choose another team member.")
    try:
        peer = db.get_document(database_id=db_id, collection_id=db_collection_id1, document_id=peer_id)
    except AppwriteException as error:
        if error.code == 404:
            raise HTTPException(404, "Team member not found.") from error
        raise
    return peer


def _public_message(message, actor_id):
    return {"id": message["$id"], "text": message["text"],
            "sender": "me" if message["sender_id"] == actor_id else "other",
            "created_at": message["$createdAt"], "read_at": message.get("read_at", "")}


@messaging_router.get("/conversations")
def conversations(actor=Depends(current_member)):
    actor_id = actor["$id"]
    outgoing = _all(MESSAGES, [Query.equal("sender_id", actor_id)])
    incoming = _all(MESSAGES, [Query.equal("recipient_id", actor_id)])
    grouped = {}
    for message in outgoing + incoming:
        peer_id = message["recipient_id"] if message["sender_id"] == actor_id else message["sender_id"]
        grouped.setdefault(peer_id, []).append(message)
    rows = []
    for user in _all(db_collection_id1, []):
        if user["$id"] == actor_id:
            continue
        history = sorted(grouped.get(user["$id"], []), key=lambda item: (item["$createdAt"], item["$id"]))
        active = user.get("status", "Active").lower() == "active"
        if not active and not history:
            continue
        last = history[-1] if history else None
        rows.append({"id": user["$id"], "name": user.get("name", "Team member"),
                     "role": user.get("role", "Farm team"), "active": active,
                     "lastMessage": last["text"] if last else "Start a conversation",
                     "updated_at": last["$createdAt"] if last else "",
                     "unread": sum(1 for item in history if item["recipient_id"] == actor_id and not item.get("read_at"))})
    rows.sort(key=lambda item: (item["updated_at"], item["name"]), reverse=True)
    return {"conversations": rows}


@messaging_router.get("/conversations/{peer_id}")
def messages(peer_id: str, actor=Depends(current_member)):
    _peer(peer_id, actor)
    # The actor is derived from the JWT; clients cannot choose another sender.
    history = _all(MESSAGES, [Query.equal("conversation_id", _conversation(actor["$id"], peer_id))])
    history.sort(key=lambda item: (item["$createdAt"], item["$id"]))
    return {"messages": [_public_message(item, actor["$id"]) for item in history]}


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    request_id: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


@messaging_router.post("/conversations/{peer_id}")
def send_message(peer_id: str, payload: MessageInput, actor=Depends(current_member)):
    peer = _peer(peer_id, actor)
    if peer.get("status", "Active").lower() != "active":
        raise HTTPException(403, "This team member cannot receive new messages.")
    text = payload.text.strip()
    if not text:
        raise HTTPException(422, "Enter a message.")
    document_id = hashlib.sha256(f"{actor['$id']}|{payload.request_id}".encode()).hexdigest()[:36]
    data = {"conversation_id": _conversation(actor["$id"], peer_id),
            "sender_id": actor["$id"], "recipient_id": peer_id, "text": text, "read_at": ""}
    try:
        saved = db.create_document(database_id=db_id, collection_id=MESSAGES,
                                   document_id=document_id, data=data)
    except AppwriteException as error:
        if error.code != 409:
            raise
        saved = db.get_document(database_id=db_id, collection_id=MESSAGES, document_id=document_id)
        if any(saved.get(key) != data[key] for key in ("sender_id", "recipient_id", "text")):
            raise HTTPException(409, "This send request was already used for another message.")
    return _public_message(saved, actor["$id"])


class ReadInput(BaseModel):
    message_ids: list[str] = Field(max_length=100)


@messaging_router.post("/conversations/{peer_id}/read")
def mark_read(peer_id: str, payload: ReadInput, actor=Depends(current_member)):
    _peer(peer_id, actor)
    now = datetime.now(timezone.utc).isoformat()
    for message_id in set(payload.message_ids):
        message = db.get_document(database_id=db_id, collection_id=MESSAGES, document_id=message_id)
        if message["recipient_id"] != actor["$id"] or message["sender_id"] != peer_id:
            raise HTTPException(403, "This message does not belong to your conversation.")
        if not message.get("read_at"):
            db.update_document(database_id=db_id, collection_id=MESSAGES,
                               document_id=message_id, data={"read_at": now})
    return {"ok": True}
