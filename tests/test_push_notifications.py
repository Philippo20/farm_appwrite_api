import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from appwrite.exception import AppwriteException
from fastapi import FastAPI
from fastapi.testclient import TestClient
import push_notifications as push
from routes.push_devices import router, current_member

class PushTests(unittest.TestCase):
    def setUp(self):
        self.db = patch.object(push, 'db').start()
        self.addCleanup(patch.stopall)
        self.actor = {'$id': 'alice', 'status': 'Active', 'role': 'admin'}
        self.token = 'device-token-' + 'x' * 40

    def test_registration_is_owned_by_authenticated_account(self):
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[current_member] = lambda: self.actor
        with patch.object(push, 'enabled', return_value=True):
            result = TestClient(app).post('/push/devices', json={'token': self.token, 'recipient_id': 'bob'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.db.create_document.call_args.kwargs['data']['recipient_id'], 'alice')

    def test_registration_rebinds_existing_installation(self):
        self.db.create_document.side_effect = AppwriteException('Conflict', 409)
        push.register(self.token, self.actor)
        self.assertEqual(self.db.update_document.call_args.kwargs['data']['recipient_id'], 'alice')

    def test_other_user_cannot_unregister_device(self):
        self.db.get_document.return_value = {'$id': 'device', 'recipient_id': 'bob'}
        push.unregister(self.token, self.actor)
        self.db.delete_document.assert_not_called()

    def test_owner_can_unregister_and_missing_is_idempotent(self):
        self.db.get_document.return_value = {'$id': 'device', 'recipient_id': 'alice'}
        push.unregister(self.token, self.actor)
        self.db.delete_document.assert_called_once()
        self.db.get_document.side_effect = AppwriteException('Missing', 404)
        push.unregister(self.token, self.actor)

    def test_disabled_queue_never_contacts_firebase(self):
        with patch.dict(os.environ, {'FCM_ENABLED': 'false'}), patch.object(push, '_pool') as pool:
            push.queue_push('alice', 'task', 'id')
            pool.submit.assert_not_called()

    def test_private_payload_and_recipient_filter(self):
        from firebase_admin import messaging
        self.db.get_document.return_value = self.actor
        devices = [{'recipient_id': 'alice', 'token': self.token, '$id': 'd1', 'updated_at': datetime.now(timezone.utc).isoformat()},
                   {'recipient_id': 'bob', 'token': 'other', '$id': 'd2'}]
        with patch.object(push, 'list_all_documents', return_value={'documents': devices}), \
             patch.object(push, 'preferences_for', return_value={'sound_alerts': False}), \
             patch.object(push, 'firebase_app', return_value=Mock()), patch.object(messaging, 'send') as send:
            push.send_push('alice', 'task', 'notice')
        message = send.call_args.args[0]
        self.assertEqual(message.data, {'recipientId': 'alice', 'eventId': 'notice', 'peerId': '__inbox__:notice', 'silent': 'true'})
        self.assertIsNone(message.notification)
        self.assertEqual(message.android.priority, 'high')
        send.assert_called_once()

    def test_muted_and_inactive_users_are_not_sent_push(self):
        from firebase_admin import messaging
        self.db.get_document.return_value = {**self.actor, 'role': 'caretaker'}
        with patch.object(push, 'preferences_for', return_value={'chat_notifications': False}), patch.object(messaging, 'send') as send:
            push.send_push('alice', 'message', 'message:id', 'peer')
            self.db.get_document.return_value = {**self.actor, 'status': 'Inactive'}
            push.send_push('alice', 'task', 'id')
            send.assert_not_called()

    def test_unregistered_token_is_removed(self):
        from firebase_admin import messaging
        self.db.get_document.return_value = self.actor
        with patch.object(push, 'list_all_documents', return_value={'documents': [
            {'$id': 'device', 'recipient_id': 'alice', 'token': self.token, 'updated_at': datetime.now(timezone.utc).isoformat()}]}), \
             patch.object(push, 'preferences_for', return_value={}), patch.object(push, 'firebase_app', return_value=Mock()), \
             patch.object(messaging, 'send', side_effect=messaging.UnregisteredError('unregistered')):
            push.send_push('alice', 'task', 'id')
        self.db.delete_document.assert_called_once()

if __name__ == '__main__': unittest.main()
