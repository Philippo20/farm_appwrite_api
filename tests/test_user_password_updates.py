import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, create_autospec
from appwrite.services.users import Users

class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

class UserPasswordUpdates(unittest.TestCase):
    def setUp(self):
        node = next(n for n in ast.parse(Path('routes/r1_users.py').read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'update_user')
        node.decorator_list = []
        node.args.defaults = []
        for arg in node.args.args: arg.annotation = None
        self.db = Mock()
        self.db.get_document.return_value = {'name': 'Test', 'email': 'test@example.com', 'role': 'admin', 'password': 'old-secret'}
        self.users = create_autospec(Users, instance=True, spec_set=True)
        self.audit = Mock()
        scope = dict(db=self.db, db_id='test', db_collection_id1='users', auth_users=self.users,
                     HTTPException=HTTPException, Role=types.SimpleNamespace(DRIVER=types.SimpleNamespace(value='driver')),
                     _validate_driver_profile=Mock(), write_audit=self.audit)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'routes/r1_users.py', 'exec'), scope)
        self.call = scope['update_user']
        self.args = dict(user_id='user', name='Test', email='test@example.com', password='', address='',
                         role=types.SimpleNamespace(value='admin'), phone='', department='', user_status='Active',
                         actor_id='admin', actor_role='admin', driver_license_number='', vehicle='', vehicle_type='', vehicle_capacity_kg=0)

    def test_approval_does_not_reset_password(self):
        self.call(**self.args)
        self.users.update_password.assert_not_called()
        self.assertNotIn('password', self.db.update_document.call_args.kwargs['data'])

    def test_appwrite_rejection_does_not_save_profile_or_report_success(self):
        self.users.update_password.side_effect = RuntimeError('Rejected')
        self.args['password'] = 'new-password'
        with self.assertRaises(HTTPException) as error: self.call(**self.args)
        self.assertEqual(error.exception.status_code, 503)
        self.db.update_document.assert_not_called()
        self.audit.assert_not_called()

    def test_explicit_password_updates_appwrite_before_profile(self):
        self.args['password'] = ' exact-password '
        order = Mock()
        order.attach_mock(self.users.update_password, 'password')
        order.attach_mock(self.db.update_document, 'profile')
        self.call(**self.args)
        self.assertEqual([c[0] for c in order.mock_calls], ['password', 'profile'])
        self.users.update_password.assert_called_once_with(user_id='user', password=' exact-password ')
        self.assertEqual(self.audit.call_args.kwargs['previous_data']['password'], '***')
