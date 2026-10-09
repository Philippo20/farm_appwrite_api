import json
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import personal_appearance as appearance


class PersonalAppearanceTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'$id': 'user-a', 'role': 'caretaker'}
        self.app = FastAPI()
        self.app.include_router(appearance.router)
        self.app.dependency_overrides[appearance.current_member] = lambda: self.actor
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_defaults_and_saved_sizes_work_for_all_roles(self):
        self.assertEqual(self.client.get('/me/appearance').json()['typography'],
            dict(headings=1, titles=1, body=1, labels=1))
        for role in ['superadmin', 'admin', 'caretaker', 'farm_owner', 'driver', 'technician']:
            self.actor.update(role=role, typography_preferences='{"body":1.2,"headings":1.3}')
            data = self.client.get('/me/appearance').json()['typography']
            self.assertEqual(data['body'], 1.2)
            self.assertEqual(data['headings'], 1.3)
            self.assertEqual(data['labels'], 1)

    def test_save_uses_authenticated_account_only_and_reopens_on_other_device(self):
        with patch.object(appearance.db, 'update_document') as save:
            payload = dict(headings=1.25, titles=1.1, body=1.15, labels=.9)
            response = self.client.put('/me/appearance', json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            args = save.call_args.kwargs
            self.assertEqual(args['document_id'], 'user-a')
            self.assertEqual(set(args['data']), {'typography_preferences'})
            self.actor.update(args['data'])
            self.assertEqual(self.client.get('/me/appearance').json()['typography'], payload)
            self.actor = {'$id': 'user-b', 'role': 'caretaker'}
            self.assertEqual(self.client.get('/me/appearance').json()['typography']['body'], 1)
            self.assertEqual(self.client.put('/me/appearance', json={**payload, 'user_id': 'user-b'}).status_code, 422)

    def test_invalid_preferences_never_write(self):
        with patch.object(appearance.db, 'update_document') as save:
            for payload in [{'headings': 0}, {'body': 5}, {'labels': '1.1'}, {'titles': True},
                            {'global': True}, {'body': -1}, {'labels': None}]:
                self.assertEqual(self.client.put('/me/appearance', json=payload).status_code, 422)
            save.assert_not_called()

    def test_auth_required_bad_stored_data_defaults_and_failures_do_not_claim_success(self):
        self.app.dependency_overrides.clear()
        self.assertEqual(self.client.get('/me/appearance').status_code, 401)
        self.assertEqual(self.client.put('/me/appearance', json={}).status_code, 401)
        self.app.dependency_overrides[appearance.current_member] = lambda: self.actor
        self.actor['typography_preferences'] = 'invalid JSON'
        self.assertEqual(self.client.get('/me/appearance').json()['typography']['titles'], 1)
        with patch.object(appearance.db, 'update_document', side_effect=RuntimeError('Private database error')):
            response = self.client.put('/me/appearance', json={})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('Private database', response.text)
