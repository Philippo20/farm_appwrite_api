import ast
import json
import os
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from cryptography.fernet import Fernet
from appwrite.exception import AppwriteException
import temporary_passwords as temporary

class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


def handler(path, name, scope):
    node = next(n for n in ast.parse(Path(path).read_text(encoding='utf-8')).body
                if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    node.returns = None
    for arg in node.args.args:
        arg.annotation = None
    node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), path, 'exec'), scope)
    return scope[name]


class TemporaryPasswordTests(unittest.TestCase):
    def setUp(self):
        self.cipher = Fernet(Fernet.generate_key())
        patcher = patch.object(temporary, 'cipher', return_value=self.cipher)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_generated_passwords_have_eight_random_mixed_characters(self):
        values = {temporary.generate_temporary_password() for _ in range(100)}
        self.assertEqual(len(values), 100)
        for value in values:
            self.assertEqual(len(value), 8)
            self.assertTrue(any(c.islower() for c in value))
            self.assertTrue(any(c.isupper() for c in value))
            self.assertTrue(any(c.isdigit() for c in value))
            self.assertTrue(any(c in '!@#$%' for c in value))

    def test_challenge_encrypted_and_tamper_rejected(self):
        token = temporary.make_challenge('u', 'p', 'session-secret')
        self.assertNotIn('session-secret', token)
        self.assertEqual(temporary.read_challenge(token)['user_id'], 'u')
        with self.assertRaises(ValueError): temporary.read_challenge('invalid')

    def test_expired_and_wrong_purpose_rejected(self):
        payload = json.dumps(dict(purpose='first_password', user_id='u', profile_id='p', session_secret='s')).encode()
        expired = self.cipher.encrypt_at_time(payload, int(time.time()) - 901).decode()
        with self.assertRaises(ValueError): temporary.read_challenge(expired)
        wrong = self.cipher.encrypt(payload.replace(b'first_password', b'another_action')).decode()
        with self.assertRaises(ValueError): temporary.read_challenge(wrong)


class FirstPasswordTests(unittest.TestCase):
    def setUp(self):
        self.db, self.account = Mock(), Mock()
        self.db.get_document.return_value = {'status': 'Active', 'must_change_password': True}
        self.account.get.return_value = {'$id': 'u'}
        self.challenge = Mock(return_value=dict(user_id='u', profile_id='p', session_secret='s'))
        self.scope = dict(HTTPException=HTTPException, AppwriteException=AppwriteException,
                         db=self.db, db_id='db', db_collection_id1='users',
                         read_challenge=self.challenge, Account=lambda _: self.account,
                         get_session_client=lambda secret: secret)
        self.call = handler('auth.py', 'change_first_password', self.scope)
        policy = patch.dict(sys.modules, {'routes.r18_system_config': types.SimpleNamespace(
            _get_or_create_config=lambda: {'password_min_length': 10})})
        policy.start()
        self.addCleanup(policy.stop)
        self.payload = dict(token='challenge', temporary_password='Temp123!', password='NewPassword123!')

    def test_success_clears_flag_only_after_password_change(self):
        result = self.call(self.payload)
        self.assertNotIn('jwt', result)
        self.account.update_password.assert_called_once_with(password='NewPassword123!', old_password='Temp123!')
        self.db.update_document.assert_called_once_with('db', 'users', 'p', {'must_change_password': False, 'password': ''})
        self.account.delete_sessions.assert_called_once()

    def test_wrong_temporary_password_preserves_requirement(self):
        self.account.update_password.side_effect = AppwriteException('Invalid credentials', 401)
        with self.assertRaises(HTTPException): self.call(self.payload)
        self.db.update_document.assert_not_called()

    def test_replay_and_suspended_accounts_blocked(self):
        for profile in ({'status': 'Active', 'must_change_password': False},
                        {'status': 'Suspended', 'must_change_password': True}):
            self.db.get_document.return_value = profile
            with self.assertRaises(HTTPException): self.call(self.payload)
        self.account.update_password.assert_not_called()

    def test_configured_minimum_and_same_password_rejected(self):
        for password in ('Short123!', 'Temp123!'):
            with self.assertRaises(HTTPException): self.call({**self.payload, 'password': password})
        self.account.update_password.assert_not_called()

    def test_expired_challenge_and_wrong_identity_blocked(self):
        self.challenge.side_effect = ValueError('expired')
        with self.assertRaises(HTTPException): self.call(self.payload)
        self.challenge.side_effect = None
        self.account.get.return_value = {'$id': 'other'}
        with self.assertRaises(HTTPException): self.call(self.payload)
        self.account.update_password.assert_not_called()


class CreationTests(unittest.TestCase):
    def setUp(self):
        from enum import Enum
        class Role(str, Enum):
            SUPERADMIN = 'superadmin'
            ADMIN = 'admin'
            DRIVER = 'driver'
        self.role = Role
        self.db, self.account, self.users, self.email = Mock(), Mock(), Mock(), Mock()
        self.db.list_documents.side_effect = [
            {'documents': [{'$id': 'admin', 'role': 'admin', 'status': 'Active'}]}, {'total': 0}]
        self.db.create_document.return_value = {'$id': 'new'}
        self.scope = dict(db=self.db, db_id='db', db_collection_id1='users', Query=Mock(),
                         Role=Role, HTTPException=HTTPException, account=self.account, auth_users=self.users,
                         _validate_driver_manager=Mock(), _validate_driver_profile=Mock(),
                         generate_temporary_password=lambda: 'Temp123!', cipher=Mock(),
                         send_email=self.email, write_audit=Mock(), ID=Mock(), status=Mock())
        self.scope['ID'].unique.return_value = 'new'
        self.call = handler('routes/r1_users.py', 'register_user', self.scope)
        settings = patch.dict(sys.modules, {'routes.email_settings': types.SimpleNamespace(
            load_settings=lambda: {'enabled': True, 'host': 'smtp.example.com', 'sender_email': 'test@example.com'})})
        settings.start()
        self.addCleanup(settings.stop)
        self.args = dict(name='New user', email='NEW@example.com', address='', role=Role.ADMIN,
                         phone='', department='', actor={'email': 'admin@example.com'},
                         user_status='Active', driver_license_number='', vehicle='', vehicle_type='')

    def test_generated_password_only_sent_in_email_not_profile_or_response(self):
        result = self.call(**self.args)
        self.assertEqual(self.account.create.call_args.kwargs['password'], 'Temp123!')
        data = self.db.create_document.call_args.kwargs['data']
        self.assertEqual(data['password'], '')
        self.assertTrue(data['must_change_password'])
        self.assertNotIn('Temp123!', json.dumps(result))
        self.assertIn('Temp123!', self.email.call_args.args[3])
        self.assertEqual(self.email.call_args.args[1], 'new@example.com')

    def test_smtp_failure_rolls_back_account_and_profile(self):
        self.email.side_effect = RuntimeError('SMTP failed')
        with self.assertRaises(HTTPException): self.call(**self.args)
        self.users.delete.assert_called_once_with(user_id='new')
        self.db.delete_document.assert_called_once_with('db', 'users', 'new')

    def test_admin_cannot_create_superadmin(self):
        with self.assertRaises(HTTPException): self.call(**{**self.args, 'role': self.role.SUPERADMIN})
        self.account.create.assert_not_called()

    def test_non_admin_blocked_even_with_forged_actor_role(self):
        self.db.list_documents.side_effect = [{'documents': [{'$id': 'other', 'role': 'caretaker', 'status': 'Active'}]}]
        with self.assertRaises(HTTPException): self.call(**self.args, actor_role='superadmin')
        self.account.create.assert_not_called()


class LoginChallengeTests(unittest.TestCase):
    def test_first_login_never_issues_dashboard_session(self):
        import uuid
        account, db = Mock(), Mock()
        account.create_email_password_session.return_value = {'userId': 'u', '$id': 'session', 'secret': 'secret'}
        db.list_documents.return_value = {'total': 1, 'documents': [{'$id': 'u', 'status': 'Active', 'must_change_password': True}]}
        scope = dict(uuid=uuid, os=os, json=json, db=db, db_id='db', db_collection_id1='users',
                     HTTPException=HTTPException, AppwriteException=AppwriteException, Query=Mock(),
                     Account=lambda _: account, Client=Mock(), get_server_client=Mock(),
                     make_challenge=Mock(return_value='encrypted-challenge'), login_logger=Mock())
        call = handler('auth.py', 'login_user', scope)
        result = call('user@example.com', 'Temp123!')
        self.assertEqual(result['password_change_token'], 'encrypted-challenge')
        for key in ('jwt', 'session_id', 'user', 'secret'):
            self.assertNotIn(key, result)
        account.create_jwt.assert_not_called()

    def test_existing_account_still_receives_normal_session(self):
        import uuid
        account, db = Mock(), Mock()
        account.create_email_password_session.return_value = {'userId': 'u', '$id': 'session', 'secret': 'secret'}
        account.create_jwt.return_value = {'jwt': 'jwt'}
        db.list_documents.return_value = {'total': 1, 'documents': [{'$id': 'u', 'status': 'Active'}]}
        scope = dict(uuid=uuid, os=os, json=json, db=db, db_id='db', db_collection_id1='users',
                     HTTPException=HTTPException, AppwriteException=AppwriteException, Query=Mock(),
                     Account=lambda _: account, Client=Mock(), get_server_client=Mock(), login_logger=Mock())
        result = handler('auth.py', 'login_user', scope)('user@example.com', 'Password123!')
        self.assertEqual(result['jwt'], 'jwt')

if __name__ == '__main__':
    unittest.main()
