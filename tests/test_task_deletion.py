import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from appwrite.exception import AppwriteException

class TaskDeletionTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'$id': 'admin-actor', 'role': 'admin'}
        def member():
            if self.actor is None: raise HTTPException(401, 'Sign in')
            return self.actor
        self.db, self.audit, self.notify = Mock(), Mock(return_value='audit-id'), Mock()
        self.previous = {'$id': 'task', 'task_id': 'FT-1', 'title': 'Clean equipment', 'farm_name': 'East',
                         'assigned_by_id': 'manager', 'assigned_to_id': 'tech', 'status': 'Pending'}
        self.db.get_document.return_value = self.previous
        spec = importlib.util.spec_from_file_location('task_test_routes', Path('routes/r23_farm_tasks.py'))
        self.route = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            'main': types.SimpleNamespace(db_id='db', db_collection_id23='tasks', db_collection_id6='audits'),
            'db': types.SimpleNamespace(db=self.db), 'audit_utils': types.SimpleNamespace(write_audit=self.audit),
            'routes.messaging': types.SimpleNamespace(current_member=member),
            'routes.r25_notifications': types.SimpleNamespace(create_notification=self.notify)}):
            spec.loader.exec_module(self.route)
        app = FastAPI(); app.include_router(self.route.collection23_router)
        self.client = TestClient(app); self.addCleanup(self.client.close)

    def delete(self): return self.client.delete('/farm-tasks/task')

    def test_only_active_selected_admin_roles_can_delete(self):
        for role in ['caretaker', 'technician', 'farm_manager', 'farm_owner', 'sales_manager']:
            self.actor['role'] = role
            self.assertEqual(self.delete().status_code, 403)
        self.actor = None
        self.assertEqual(self.delete().status_code, 401)
        self.db.delete_document.assert_not_called()
        self.audit.assert_not_called()

    def test_both_admins_audit_authenticated_actor_not_original_assigner(self):
        for role in ['admin', 'superadmin']:
            self.actor['role'] = role
            result = self.delete()
            self.assertEqual(result.status_code, 200, result.text)
            audit = self.audit.call_args.kwargs
            self.assertEqual(audit['performed_by_id'], 'admin-actor')
            self.assertEqual(audit['performed_by_role'], role)
            self.assertEqual(audit['previous_data']['id'], 'task')
            self.assertEqual(audit['status'], 'Pending')
            self.assertTrue(audit['strict'])
            self.assertEqual(self.db.update_document.call_args.kwargs['data']['status'], 'Success')
        self.notify.assert_called()

    def test_logging_failure_keeps_task(self):
        self.audit.side_effect = RuntimeError('Audit unavailable')
        self.assertEqual(self.delete().status_code, 503)
        self.db.delete_document.assert_not_called()

    def test_delete_failure_marks_audit_failed_without_notifying(self):
        self.db.delete_document.side_effect = RuntimeError('Database down')
        self.assertEqual(self.delete().status_code, 503)
        self.assertEqual(self.db.update_document.call_args.kwargs['data']['status'], 'Failed')
        self.notify.assert_not_called()

    def test_final_log_failure_reports_pending_but_does_not_retry_deletion(self):
        self.db.update_document.side_effect = RuntimeError('Database down')
        result = self.delete()
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['audit_pending'])
        self.db.delete_document.assert_called_once()

    def test_missing_task_returns_not_found(self):
        self.db.get_document.side_effect = AppwriteException('Missing', 404)
        self.assertEqual(self.delete().status_code, 404)
        self.audit.assert_not_called()
