import importlib.util
import sys
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from workflow_notifications import events_for, publish_event, sensor_band
from operational_reminders import maintenance_events


class PolicyTests(unittest.TestCase):
    def test_preferences_mute_delivery_without_removing_inbox(self):
        from notification_preferences import delivery_options
        self.assertEqual(delivery_options('message', {'chat_notifications': False, 'sound_alerts': False}),
                         {'delivery_enabled': False, 'silent': True})
        self.assertTrue(delivery_options('financial', {'task_reminders': False})['delivery_enabled'])

    def test_daily_monitoring_issues_notify_without_batch_progress(self):
        event = events_for('Farm Records', 'Create', None, {'has_issues': True, 'farm_id': 'f1', 'record_type': 'daily_monitoring', 'issue_severity': 'critical'})[0]
        self.assertEqual(event['farm'], 'f1')
        self.assertIn('admin', event['roles'])
        self.assertEqual(event['priority'], 'urgent')

    def test_funds_only_on_status_change_and_private_decisions(self):
        request = {'$id': 'fund', 'status': 'Pending', 'requested_by_id': 'manager'}
        self.assertEqual(events_for('Fund Requests', 'Update', request, {'purpose': 'New description'}), [])
        approved = events_for('Fund Requests', 'Update', request, {'status': 'Approved'})[0]
        self.assertEqual(approved['recipients'], {'manager'})
        self.assertEqual(approved['kind'], 'fund_request')
        self.assertEqual(approved['roles'], set())

    def test_sensor_inclusive_boundaries_and_no_repeated_bad_readings(self):
        sensor = {'value': 10, 'range_min': 10, 'range_max': 30, 'alerts_enabled': True, 'farmID': 'f1'}
        self.assertEqual(sensor_band(sensor), 'normal')
        self.assertEqual(events_for('Sensor readings', 'Update', sensor, {'value': 31})[0]['kind'], 'sensor_alert')
        self.assertEqual(sensor_band({**sensor, 'value': 30}), 'normal')
        self.assertEqual(len(events_for('Sensor readings', 'Update', sensor, {'value': 31})), 1)
        self.assertEqual(events_for('Sensor readings', 'Update', {**sensor, 'value': 31}, {'value': 32}), [])
        self.assertEqual(events_for('Sensor readings', 'Update', sensor, {'value': 31, 'alerts_enabled': False}), [])

    def test_farm_assignment_only_new_assignee(self):
        result = events_for('Farms', 'Update', {'caretakerID': 'old', 'name': 'A'}, {'caretakerID': 'new'})
        self.assertEqual(result[0]['recipients'], {'new'})
        self.assertEqual(events_for('Farms', 'Update', {'name': 'A'}, {'location': 'B'}), [])

    def test_inventory_only_crossing_reorder_threshold(self):
        data = {'quantity_available': 8, 'reorder_level': 5}
        self.assertEqual(len(events_for('Inventory', 'Update', data, {'quantity_available': 5})), 1)
        self.assertEqual(events_for('Inventory', 'Update', {**data, 'quantity_available': 4}, {'quantity_available': 3}), [])

    def test_deadline_key_changes_only_at_due_state_or_occurrence(self):
        device = {'$id': 'd', 'farmID': 'f', 'maintenance_plan': [
            {'id': 'p', 'type': 'cleaning', 'interval_days': 14, 'first_due': '2026-10-06', 'assigned_to_id': 'tech'}]}
        first = list(maintenance_events([device], [], date(2026, 10, 2)))
        second = list(maintenance_events([device], [], date(2026, 10, 3)))
        self.assertEqual(first[0][0], second[0][0])
        due = list(maintenance_events([device], [], date(2026, 10, 6)))
        self.assertNotEqual(first[0][0], due[0][0])
        completed = [{'device_id': 'd', 'plan_id': 'p', 'completed_on': '2026-10-06'}]
        self.assertEqual(list(maintenance_events([device], completed, date(2026, 10, 6))), [])

    def test_fanout_excludes_unassigned_and_inactive_users_and_is_idempotent(self):
        db = Mock()
        db.get_document.return_value = {'ownerID': 'owner', 'caretakerID': 'keeper'}
        users = [{'$id': who, 'status': status, 'role': role} for who, status, role in [
            ('owner', 'Active', 'farm_owner'), ('keeper', 'Inactive', 'caretaker'),
            ('admin', 'Active', 'admin'), ('other', 'Active', 'caretaker')]]
        main = types.SimpleNamespace(db_id='db', db_collection_id1='users', db_collection_id2='farms', db_collection_id25='notifications')
        with patch.dict(sys.modules, {'db': types.SimpleNamespace(db=db), 'main': main}), \
             patch('document_paging.list_all_documents', return_value={'documents': users}):
            event = {'title': 'Test', 'message': 'Safe', 'farm': 'f1', 'roles': {'admin'}}
            publish_event('event1', event)
            calls = db.create_document.call_args_list
            self.assertEqual({c.kwargs['data']['recipient_id'] for c in calls}, {'owner', 'admin'})
            ids = [c.kwargs['document_id'] for c in calls]
            db.reset_mock()
            publish_event('event1', event)
            self.assertEqual(ids, [c.kwargs['document_id'] for c in db.create_document.call_args_list])


class InboxAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        def actor(): return {'$id': 'alice'}
        stubs = {'db': types.SimpleNamespace(db=self.db),
                 'main': types.SimpleNamespace(db_id='db', db_collection_id25='notifications'),
                 'notification_email': types.SimpleNamespace(queue_notification_email=Mock()),
                 'routes.messaging': types.SimpleNamespace(current_member=actor)}
        spec = importlib.util.spec_from_file_location('notification_test_routes', Path(__file__).parents[1] / 'routes/r25_notifications.py')
        self.route = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, stubs): spec.loader.exec_module(self.route)
        app = FastAPI()
        app.include_router(self.route.collection25_router)
        self.client = TestClient(app)

    def test_cannot_read_or_mark_other_recipient(self):
        for method, url in [('get', '/notifications?recipient_id=bob'), ('patch', '/notifications/read-all?recipient_id=bob')]:
            self.assertEqual(getattr(self.client, method)(url).status_code, 403)
        self.db.get_document.return_value = {'recipient_id': 'bob'}
        self.assertEqual(self.client.patch('/notifications/n1/read').status_code, 404)
        self.db.update_document.assert_not_called()

    def test_own_inbox_is_filtered_and_can_mark_read(self):
        self.db.list_documents.return_value = {'documents': [{'$id': 'n1', 'recipient_id': 'alice'}]}
        self.assertEqual(self.client.get('/notifications?recipient_id=alice').status_code, 200)
        self.assertIn('alice', str(self.db.list_documents.call_args.kwargs['queries']))
        self.db.get_document.return_value = {'recipient_id': 'alice'}
        self.db.update_document.return_value = {'$id': 'n1', 'is_read': True}
        self.assertEqual(self.client.patch('/notifications/n1/read').status_code, 200)


if __name__ == '__main__': unittest.main()
