"""Exercise the production session handler with isolated Appwrite dependencies."""
import ast
import datetime
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch, create_autospec
from appwrite.services.users import Users
from appwrite.services.account import Account


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code


class SessionTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path('auth.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'refresh_session')
        function.decorator_list = []
        self.account = create_autospec(Account, instance=True, spec_set=True)
        self.account.get.return_value = {'$id': 'alice', 'email': 'alice@test.com'}
        self.users = create_autospec(Users, instance=True, spec_set=True)
        self.users.list_sessions.return_value = {'sessions': [{'$id': 'verified-session', 'expire': '2099-01-01T00:00:00Z'}]}
        self.users.create_jwt.return_value = {'jwt': 'renewed'}
        self.db = Mock()
        self.db.list_documents.return_value = {'documents': [{'status': 'Active'}]}
        self.claims = Mock()
        self.claims.decode.return_value = {'sessionId': 'verified-session'}
        self.scope = dict(Header=lambda **_: '', HTTPException=HTTPException,
                          Account=lambda _: self.account, Users=lambda _: self.users,
                          get_user_client_from_jwt=lambda t: t, get_server_client=lambda: None,
                          jwt=self.claims, db=self.db, db_id='test', db_collection_id1='users',
                          Query=Mock(), datetime=datetime, AppwriteException=type('AppwriteException', (Exception,), {}))
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'auth.py', 'exec'), self.scope)
        self.policy = patch.dict(sys.modules, {'routes.r18_system_config': types.SimpleNamespace(
            _get_or_create_config=lambda: {'session_timeout': 10, 'session_idle_warning_minutes': 2, 'sensor_ingest_api_key': 'secret'})})
        self.policy.start()
        self.addCleanup(self.policy.stop)

    def call(self, token='Bearer verified'):
        return self.scope['refresh_session'](token)

    def test_refresh_bound_to_verified_session_and_public_policy_only(self):
        self.assertEqual(self.call(), {'jwt': 'renewed', 'session_timeout': 10, 'session_idle_warning_minutes': 2})
        self.users.create_jwt.assert_called_once_with(user_id='alice', session_id='verified-session', duration=900)

    def test_missing_token_rejected(self):
        with self.assertRaises(HTTPException) as error: self.call('')
        self.assertEqual(error.exception.status_code, 401)
        self.account.get.assert_not_called()

    def test_expired_session_cannot_be_renewed(self):
        self.users.list_sessions.return_value = {'sessions': [{'$id': 'verified-session', 'expire': '2020-01-01T00:00:00Z'}]}
        with self.assertRaises(HTTPException) as error: self.call()
        self.assertEqual(error.exception.status_code, 401)
        self.users.create_jwt.assert_not_called()

    def test_inactive_account_cannot_continue(self):
        self.db.list_documents.return_value = {'documents': [{'status': 'Inactive'}]}
        with self.assertRaises(HTTPException) as error: self.call()
        self.assertEqual(error.exception.status_code, 403)
        self.users.create_jwt.assert_not_called()

    def test_authentication_precedes_claim_inspection(self):
        self.account.get.side_effect = HTTPException(401, 'Revoked')
        with self.assertRaises(HTTPException): self.call()
        self.claims.decode.assert_not_called()
        self.users.create_jwt.assert_not_called()

    def test_server_key_permission_error_does_not_expire_valid_user(self):
        error = self.scope['AppwriteException']('Missing server scope')
        error.code = 401
        self.users.create_jwt.side_effect = error
        with self.assertRaises(HTTPException) as result: self.call()
        self.assertEqual(result.exception.status_code, 503)

    def test_revoked_jwt_is_still_rejected(self):
        error = self.scope['AppwriteException']('Invalid JWT')
        error.code = 401
        self.account.get.side_effect = error
        with self.assertRaises(HTTPException) as result: self.call()
        self.assertEqual(result.exception.status_code, 401)
        self.users.create_jwt.assert_not_called()

    def test_missing_session_is_still_rejected(self):
        error = self.scope['AppwriteException']('Session gone')
        error.code = 404
        error.type = 'user_session_not_found'
        self.users.list_sessions.side_effect = error
        with self.assertRaises(HTTPException) as result: self.call()
        self.assertEqual(result.exception.status_code, 401)

    def test_different_session_cannot_replace_token_session(self):
        self.users.list_sessions.return_value = {'sessions': [{'$id': 'another', 'expire': '2099-01-01T00:00:00Z'}]}
        with self.assertRaises(HTTPException) as result: self.call()
        self.assertEqual(result.exception.status_code, 401)
        self.users.create_jwt.assert_not_called()

class LoginTests(unittest.TestCase):
    def setUp(self):
        SessionTests.setUp(self)
        tree = ast.parse(Path('auth.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'login_user')
        function.decorator_list = []
        for arg in function.args.args:
            arg.annotation = None
        from appwrite.client import Client
        self.client = create_autospec(Client, instance=True, spec_set=True)
        self.scope.update(Client=lambda: self.client, os=types.SimpleNamespace(getenv=lambda *args: 'test'))
        self.account.create_email_password_session.return_value = {'$id': 'new-session', 'secret': 'session-secret'}
        self.account.create_jwt.return_value = {'jwt': 'fresh-token'}
        self.db.list_documents.return_value = {'total': 1, 'documents': [{'status': 'Active', 'email': 'new@example.com'}]}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'auth.py', 'exec'), self.scope)

    def test_new_user_login_preserves_password_and_normalizes_email(self):
        result = self.scope['login_user'](' New@Example.com ', ' password with spaces ')
        self.account.create_email_password_session.assert_called_once_with(email='new@example.com', password=' password with spaces ')
        self.assertEqual(result['jwt'], 'fresh-token')
        self.assertEqual(result['session_id'], 'new-session')

    def test_profile_failure_is_not_invalid_credentials(self):
        self.db.list_documents.side_effect = RuntimeError('Database unavailable')
        with self.assertRaises(HTTPException) as result:
            self.scope['login_user']('new@example.com', 'password')
        self.assertEqual(result.exception.status_code, 503)

    def test_wrong_password_remains_401(self):
        error = self.scope['AppwriteException']('Wrong password')
        error.code = 401
        error.type = 'user_invalid_credentials'
        self.account.create_email_password_session.side_effect = error
        with self.assertRaises(HTTPException) as result:
            self.scope['login_user']('new@example.com', 'wrong')
        self.assertEqual(result.exception.status_code, 401)
