import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

class NotificationEmailTest(unittest.TestCase):
    def setUp(self):
        database = types.ModuleType('db')
        database.db = Mock()
        main = types.ModuleType('main')
        main.db_id = 'db'
        main.db_collection_id18 = 'config'
        main.db_collection_id1 = 'users'
        spec = importlib.util.spec_from_file_location('notification_email_under_test', Path(__file__).parents[1] / 'notification_email.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'db': database, 'main': main}):
            spec.loader.exec_module(self.module)
        self.addCleanup(self.module._pool.shutdown)
        self.module._slots = Mock()
        self.module.send_email = Mock()
        self.db = database.db

    def test_global_switch_prevents_email(self):
        self.db.get_document.return_value = {'email_notifications': False}
        self.module._deliver('user', 'Title', 'Body', 'task')
        self.module.send_email.assert_not_called()
        self.assertEqual(self.db.get_document.call_count, 1)

    def test_category_and_active_recipient_used(self):
        self.db.get_document.side_effect = [{'email_notifications': True}, {'email_settings_json': json.dumps({'enabled': True, 'farm_alerts': True})}, {'status': 'Active', 'email': 'recipient@example.com', 'name': 'Ama', 'role': 'farm_manager'}]
        self.module._deliver('user', 'Title', 'Body', 'batch')
        self.assertEqual(self.module.send_email.call_args.args[-1], 'farm_alerts')
        self.assertEqual(self.module.send_email.call_args.args[1], 'recipient@example.com')
        self.assertEqual(self.module.send_email.call_args.kwargs, {'recipient_name': 'Ama', 'recipient_role': 'farm_manager'})

    def test_disabled_category_prevents_email(self):
        self.db.get_document.side_effect = [{'email_notifications': True}, {'email_settings_json': json.dumps({'enabled': True, 'workflow_alerts': False})}]
        self.module._deliver('user', 'Title', 'Body', 'task')
        self.module.send_email.assert_not_called()

    def test_failure_is_contained(self):
        self.db.get_document.side_effect = RuntimeError('unavailable')
        with self.assertLogs(self.module._log, level='WARNING'):
            self.module._deliver('user', 'Title', 'Body', 'task')
        self.module._slots.release.assert_called_once()
