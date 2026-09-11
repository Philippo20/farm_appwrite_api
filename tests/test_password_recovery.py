import ast
import os
import sys
import types
import unittest
from recovery_diagnostics import log_recovery_failure
from recovery_url import password_reset_url
from pathlib import Path
from unittest.mock import Mock, patch

class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail

class AppwriteException(Exception):
    def __init__(self, code, kind=''):
        self.code, self.type = code, kind

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        nodes = [n for n in ast.parse(Path('auth.py').read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name in {'create_password_recovery', 'confirm_password_recovery'}]
        for node in nodes:
            node.decorator_list = []
            node.args.defaults = []
            for arg in node.args.args: arg.annotation = None
        self.account = Mock()
        self.scope = {'_recovery_account': lambda: self.account, 'HTTPException': HTTPException, 'AppwriteException': AppwriteException, 'os': os, 'log_recovery_failure': log_recovery_failure, 'password_reset_url': password_reset_url}
        config = types.ModuleType('routes.r18_system_config')
        config._get_or_create_config = lambda: {'password_min_length': 10}
        self.modules = patch.dict(sys.modules, {'routes.r18_system_config': config})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'auth.py', 'exec'), self.scope)

    def test_unknown_email_does_not_reveal_account_existence(self):
        expected = self.scope['create_password_recovery']('user@example.com')
        self.account.create_recovery.side_effect = AppwriteException(404, 'user_not_found')
        self.assertEqual(self.scope['create_password_recovery']('unknown@example.com'), expected)

    def test_legacy_fragment_is_converted_before_appwrite_request(self):
        with patch.dict(os.environ, {'PASSWORD_RESET_URL': 'https://apps.farmestates.farm/#/reset-password'}):
            self.scope['create_password_recovery']('user@example.com')
        self.assertEqual(self.account.create_recovery.call_args.kwargs['url'],
                         'https://apps.farmestates.farm/?recovery=1')

    def test_custom_reset_path_is_preserved(self):
        with patch.dict(os.environ, {'PASSWORD_RESET_URL': 'https://example.com/reset-password'}):
            self.assertEqual(password_reset_url(), 'https://example.com/reset-password')

    def test_flutter_base_path_and_query_are_preserved(self):
        with patch.dict(os.environ, {'PASSWORD_RESET_URL': 'https://example.com/app/?lang=en#/reset-password'}):
            self.assertEqual(password_reset_url(), 'https://example.com/app/?lang=en&recovery=1')

    def test_mail_service_failure_not_reported_as_success(self):
        self.account.create_recovery.side_effect = AppwriteException(500)
        with self.assertRaises(HTTPException) as caught: self.scope['create_password_recovery']('user@example.com')
        self.assertEqual(caught.exception.status_code, 503)

    def test_confirm_uses_token_and_password_body(self):
        self.scope['confirm_password_recovery']({'user_id': 'user', 'secret': 'one-use-token', 'password': 'valid-password'})
        self.account.update_recovery.assert_called_once_with(user_id='user', secret='one-use-token', password='valid-password')

    def test_short_password_rejected(self):
        with self.assertRaises(HTTPException): self.scope['confirm_password_recovery']({'user_id': 'user', 'secret': 'token', 'password': 'short'})
        self.account.update_recovery.assert_not_called()

    def test_expired_token_rejected(self):
        self.account.update_recovery.side_effect = AppwriteException(401)
        with self.assertRaises(HTTPException) as caught: self.scope['confirm_password_recovery']({'user_id': 'user', 'secret': 'expired', 'password': 'valid-password'})
        self.assertEqual(caught.exception.status_code, 400)

    def test_project_not_found_is_not_silently_reported_as_success(self):
        self.account.create_recovery.side_effect = AppwriteException(404, 'project_not_found')
        with self.assertLogs('uvicorn.error') as logs:
            with self.assertRaises(HTTPException) as caught:
                self.scope['create_password_recovery']('user@example.com')
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn('project_not_found', logs.output[0])
        self.assertIn('Reference:', caught.exception.detail)

    def test_smtp_diagnostic_excludes_private_provider_message(self):
        error = AppwriteException(503, 'general_smtp_disabled')
        error.args = ('private@example.com secret-token smtp-password',)
        self.account.create_recovery.side_effect = error
        with self.assertLogs('uvicorn.error') as logs:
            with self.assertRaises(HTTPException):
                self.scope['create_password_recovery']('private@example.com')
        output = logs.output[0]
        self.assertIn('general_smtp_disabled', output)
        for private in ('private@example.com', 'secret-token', 'smtp-password'):
            self.assertNotIn(private, output)

    def test_transport_failure_returns_reference(self):
        self.account.create_recovery.side_effect = ConnectionError('private endpoint')
        with self.assertLogs('uvicorn.error'):
            with self.assertRaises(HTTPException) as caught:
                self.scope['create_password_recovery']('user@example.com')
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn('Reference:', caught.exception.detail)

    def test_rate_limit_is_preserved(self):
        self.account.create_recovery.side_effect = AppwriteException(429, 'general_rate_limit_exceeded')
        with self.assertLogs('uvicorn.error'):
            with self.assertRaises(HTTPException) as caught:
                self.scope['create_password_recovery']('user@example.com')
        self.assertEqual(caught.exception.status_code, 429)
