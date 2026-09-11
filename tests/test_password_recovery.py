import ast
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail

class AppwriteException(Exception):
    def __init__(self, code): self.code = code

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        nodes = [n for n in ast.parse(Path('auth.py').read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name in {'create_password_recovery', 'confirm_password_recovery'}]
        for node in nodes:
            node.decorator_list = []
            node.args.defaults = []
            for arg in node.args.args: arg.annotation = None
        self.account = Mock()
        self.scope = {'_recovery_account': lambda: self.account, 'HTTPException': HTTPException, 'AppwriteException': AppwriteException, 'os': os}
        config = types.ModuleType('routes.r18_system_config')
        config._get_or_create_config = lambda: {'password_min_length': 10}
        self.modules = patch.dict(sys.modules, {'routes.r18_system_config': config})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'auth.py', 'exec'), self.scope)

    def test_unknown_email_does_not_reveal_account_existence(self):
        expected = self.scope['create_password_recovery']('user@example.com')
        self.account.create_recovery.side_effect = AppwriteException(404)
        self.assertEqual(self.scope['create_password_recovery']('unknown@example.com'), expected)

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
