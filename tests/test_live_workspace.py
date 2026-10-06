import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import importlib.util
import sys
import types
from pathlib import Path
spec = importlib.util.spec_from_file_location('live_test_routes', Path(__file__).parents[1] / 'routes/live_workspace.py')
live = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'routes.messaging': types.SimpleNamespace(current_member=lambda: None)}):
    spec.loader.exec_module(live)


class LiveWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'$id': 'reviewer', 'role': 'accountant', 'name': 'Reviewer'}
        app = FastAPI()
        app.include_router(live.router)
        app.dependency_overrides[live.current_member] = lambda: self.actor
        self.client = TestClient(app)
        self.db = patch.object(live, 'db').start()
        self.audit = patch.object(live, 'write_audit').start()
        self.addCleanup(patch.stopall)
        self.record = {'$id': 'request', '$updatedAt': 'v1', 'status': 'Pending',
                       'requested_by_id': 'manager', 'amount': 500, 'currency': 'GHS'}
        self.db.get_document.return_value = self.record
        self.db.update_document.side_effect = lambda **kwargs: {**self.record, **kwargs['data']}

    def test_queue_excludes_balance_and_payout_accounts(self):
        with patch.object(live, '_rows', side_effect=[
            [self.record], [{'$id': 'wallet', 'transaction_type': 'Balance'},
            {'$id': 'withdrawal', 'transaction_type': 'Withdrawal', 'withdrawal_status': 'Pending'}]]):
            result = self.client.get('/accountant/approvals')
        self.assertEqual(result.status_code, 200)
        self.assertEqual([r['kind'] for r in result.json()['users']], ['fund_request', 'withdrawal'])
        self.assertNotIn('account_number', result.text)

    def test_unauthorized_role_cannot_read_or_review(self):
        self.actor['role'] = 'caretaker'
        self.assertEqual(self.client.get('/accountant/approvals').status_code, 403)
        self.assertEqual(self.decide().status_code, 403)
        self.db.update_document.assert_not_called()

    def decide(self, decision='Approved', notes='', revision='v1', kind='fund_request'):
        return self.client.patch(f'/accountant/approvals/{kind}/request',
                                 json={'decision': decision, 'notes': notes, 'revision': revision})

    def test_save_preserves_amount_and_records_authenticated_reviewer(self):
        self.assertEqual(self.decide().status_code, 200)
        data = self.db.update_document.call_args.kwargs['data']
        self.assertEqual(data['approved_by_id'], 'reviewer')
        self.assertEqual(data['status'], 'Approved')
        self.assertNotIn('amount', data)
        self.assertEqual(self.audit.call_args.kwargs['performed_by_role'], 'accountant')

    def test_reject_requires_reason(self):
        self.assertEqual(self.decide('Rejected').status_code, 422)
        self.db.update_document.assert_not_called()
        self.assertEqual(self.decide('Rejected', 'Outside budget').status_code, 200)

    def test_stale_or_decided_request_is_not_overwritten(self):
        self.assertEqual(self.decide(revision='old').status_code, 409)
        self.record['status'] = 'Approved'
        self.assertEqual(self.decide().status_code, 409)
        self.db.update_document.assert_not_called()

    def test_self_approval_and_payment_are_not_allowed(self):
        self.record['requested_by_id'] = 'reviewer'
        self.assertEqual(self.decide().status_code, 403)
        self.assertEqual(self.decide('Paid').status_code, 422)
        self.db.update_document.assert_not_called()

    def test_withdrawal_decision_does_not_change_balance(self):
        self.record.update(transaction_type='Withdrawal', withdrawal_status='Pending', user_id='owner')
        self.assertEqual(self.decide(kind='withdrawal').status_code, 200)
        data = self.db.update_document.call_args.kwargs['data']
        self.assertEqual(data['withdrawal_status'], 'Approved')
        self.assertNotIn('balance', data)
        self.assertEqual(self.audit.call_args.kwargs['collection_name'], 'Wallet')

    def test_calendar_filters_assignments_and_uses_saved_dates(self):
        self.actor = {'$id': 'care', 'role': 'caretaker'}
        with patch.object(live, '_rows', side_effect=[
            [{'$id': 'farm', 'caretakerID': 'care', 'name': 'My farm'}, {'$id': 'other', 'caretakerID': 'other'}],
            [{'$id': 'direct', 'assigned_to_id': 'care', 'due_date': '2026-10-06'},
             {'$id': 'shared', 'assigned_to_id': '', 'farm_id': 'farm', 'due_date': '2026-10-07'},
             {'$id': 'private', 'assigned_to_id': 'other', 'farm_id': 'farm', 'due_date': '2026-10-07'},
             {'$id': 'undated', 'assigned_to_id': 'care'},
             {'$id': 'outside', 'assigned_to_id': '', 'farm_id': 'other', 'due_date': '2026-10-07'}],
            [{'$id': 'batch', 'farmID': 'farm', 'end_date': '2026-10-20', 'batch_no': 'B-123'},
             {'$id': 'outside', 'farmID': 'other', 'end_date': '2026-10-20'}]]):
            result = self.client.get('/caretaker/calendar')
        self.assertEqual(result.status_code, 200)
        rows = result.json()['users']
        self.assertEqual([r['id'] for r in rows], ['task:direct', 'task:shared', 'batch:batch:0'])
        self.assertEqual(rows[-1]['description'], 'Batch B-123')

    def test_calendar_rejects_other_roles(self):
        self.assertEqual(self.client.get('/caretaker/calendar').status_code, 403)

    def test_lists_use_paging_helper(self):
        with patch.object(live, 'list_all_documents', return_value={'documents': [self.record]}) as pages:
            self.assertEqual(live._rows('funds'), [self.record])
            pages.assert_called_once_with(self.db, database_id=live.db_id, collection_id='funds')


if __name__ == '__main__':
    unittest.main()
