import ast
import json
import unittest
from pathlib import Path
from unittest.mock import Mock
from fastapi import HTTPException
from user_roles import assigned_roles, effective_profile, requested_roles, check_role_assignment


class RoleTests(unittest.TestCase):
    def test_legacy_and_duplicate_roles(self):
        self.assertEqual(assigned_roles({'role': 'farm_owner'}), ['farm_owner'])
        self.assertEqual(assigned_roles({'role': 'admin', 'roles': []}), ['admin'])
        self.assertEqual(assigned_roles({'roles': ['owner', 'farm_owner', 'technician']}), ['farm_owner', 'technician'])

    def test_selection_never_mutates_primary_role(self):
        profile = {'role': 'caretaker', 'roles': ['caretaker', 'technician']}
        selected = effective_profile(profile, 'technician')
        self.assertEqual(selected['role'], 'technician')
        self.assertEqual(selected['primary_role'], 'caretaker')
        self.assertEqual(profile['role'], 'caretaker')
        with self.assertRaises(HTTPException): effective_profile(profile, 'admin')

    def test_assignment_validation_and_legacy_update_preserves_roles(self):
        profile = {'role': 'caretaker', 'roles': ['caretaker', 'technician']}
        self.assertEqual(requested_roles(None, 'caretaker', profile), profile['roles'])
        for raw in ['[]', '["invalid"]', '["technician"]', '{}', 'broken']:
            with self.assertRaises(HTTPException): requested_roles(raw, 'caretaker')
        self.assertEqual(requested_roles('["caretaker","technician"]', 'caretaker'), profile['roles'])

    def test_secondary_superadmin_cannot_be_granted_or_modified_by_admin(self):
        admin = {'role': 'admin', 'status': 'Active'}
        check_role_assignment(admin, ['caretaker', 'technician'])
        for roles, previous in [(['admin', 'superadmin'], None),
                                (['admin'], {'role': 'admin', 'roles': ['admin', 'superadmin']})]:
            with self.assertRaises(HTTPException): check_role_assignment(admin, roles, previous)
        check_role_assignment({'role': 'superadmin', 'status': 'Active'}, ['admin', 'superadmin'])
        for actor in [{'role': 'technician', 'status': 'Active'}, {'role': 'admin', 'status': 'Suspended'}]:
            with self.assertRaises(HTTPException): check_role_assignment(actor, ['admin'])

    def test_role_endpoint_checks_database_and_does_not_change_profile(self):
        tree = ast.parse(Path('auth.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'select_account_role')
        node.decorator_list = []
        node.args.defaults = []
        for arg in node.args.args: arg.annotation = None
        db = Mock()
        db.list_documents.return_value = {'documents': [{'role': 'caretaker', 'roles': ['caretaker', 'technician'], 'status': 'Active'}]}
        scope = dict(db=db, db_id='db', db_collection_id1='users', Query=Mock(), HTTPException=HTTPException, effective_profile=effective_profile)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'auth.py', 'exec'), scope)
        call = scope['select_account_role']
        self.assertEqual(call('technician', {'email': 'user@example.com'})['role'], 'technician')
        with self.assertRaises(HTTPException): call('superadmin', {'email': 'user@example.com'})
        db.update_document.assert_not_called()
        db.list_documents.return_value['documents'][0]['status'] = 'Suspended'
        with self.assertRaises(HTTPException): call('technician', {'email': 'user@example.com'})
