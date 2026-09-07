import importlib
import json
import sys
import types
import unittest
from unittest.mock import patch

from appwrite.exception import AppwriteException
from fastapi import FastAPI
from fastapi.testclient import TestClient


class MemoryDB:
    def __init__(self):
        self.users = {key: {"$id": key, "name": key, "email": key + "@farm.test", "status": "Active"}
                      for key in ("alice", "bob", "eve")}
        self.messages = {}

    def list_documents(self, collection_id, queries, **_):
        rows = list(self.users.values() if collection_id == "users" else self.messages.values())
        offset, limit = 0, 100
        for raw in queries:
            query = json.loads(raw)
            if query["method"] == "equal":
                rows = [row for row in rows if row.get(query["attribute"]) in query["values"]]
            elif query["method"] == "offset": offset = query["values"][0]
            elif query["method"] == "limit": limit = query["values"][0]
        return {"documents": rows[offset:offset+limit]}

    def get_document(self, collection_id, document_id, **_):
        rows = self.users if collection_id == "users" else self.messages
        if document_id not in rows: raise AppwriteException("Not found", 404)
        return rows[document_id]

    def create_document(self, document_id, data, **_):
        if document_id in self.messages: raise AppwriteException("Conflict", 409)
        self.messages[document_id] = {"$id": document_id, "$createdAt": "2026-09-07T10:00:00Z", **data}
        return self.messages[document_id]

    def update_document(self, document_id, data, **_):
        self.messages[document_id].update(data)
        return self.messages[document_id]


class MessagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import the real route with isolated database/auth dependencies; never use production data.
        deps = {"main": types.SimpleNamespace(db_id="test", db_collection_id1="users"),
                "db": types.SimpleNamespace(db=None),
                "auth": types.SimpleNamespace(get_user_client_from_jwt=lambda token: token)}
        with patch.dict(sys.modules, deps):
            cls.module = importlib.import_module("routes.messaging")

    def setUp(self):
        self.db = MemoryDB()
        self.module.db = self.db
        self.app = FastAPI()
        self.app.include_router(self.module.messaging_router)
        self.client = TestClient(self.app)
        self.actor("alice")

    def actor(self, name):
        self.app.dependency_overrides[self.module.current_member] = lambda: self.db.users[name]

    def send(self, text="Hello", request_id="request_1234567890"):
        return self.client.post("/messages/conversations/bob", json={"text": text, "request_id": request_id})

    def test_persistence_isolation_and_read_receipt(self):
        saved = self.send().json()
        self.actor("bob")
        self.assertEqual(self.client.get("/messages/conversations/alice").json()["messages"][0]["text"], "Hello")
        self.assertEqual(self.client.post("/messages/conversations/alice/read", json={"message_ids": [saved["id"]]}).status_code, 200)
        self.actor("alice")
        self.assertTrue(self.client.get("/messages/conversations/bob").json()["messages"][0]["read_at"])
        self.actor("eve")
        self.assertEqual(self.client.get("/messages/conversations/bob").json()["messages"], [])
        self.assertEqual(self.client.post("/messages/conversations/alice/read", json={"message_ids": [saved["id"]]}).status_code, 403)

    def test_retry_is_idempotent_and_conflicting_retry_fails(self):
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(len(self.db.messages), 1)
        self.assertEqual(self.send("Different text").status_code, 409)

    def test_validation_and_inactive_recipient(self):
        self.assertEqual(self.send(" ").status_code, 422)
        self.assertEqual(self.send("x" * 4001).status_code, 422)
        self.db.users["bob"]["status"] = "Suspended"
        self.assertEqual(self.send().status_code, 403)

    def test_unauthenticated_access_is_denied(self):
        self.app.dependency_overrides.clear()
        self.assertEqual(self.client.get("/messages/conversations").status_code, 401)

    def test_unread_counts(self):
        self.send()
        self.actor("bob")
        chats = self.client.get("/messages/conversations").json()["conversations"]
        self.assertEqual(next(chat for chat in chats if chat["id"] == "alice")["unread"], 1)


if __name__ == "__main__":
    unittest.main()
