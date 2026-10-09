import importlib.util
import json
import sys
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from appwrite.exception import AppwriteException
from production_planning import validate_plan, schedule, reminder_events

PLAN = {'stages': [{'name': 'Sprouting', 'days': 7}, {'name': 'Leaf Development', 'days': 28},
                   {'name': 'Harvest', 'days': 7}], 'interval_days': 14, 'reminder_days': 2}


def batch(identity='b1', start='2026-10-05', farm='f1', **extra):
    return {'$id': identity, 'batch_no': identity, 'farmID': farm, 'plant_type_ID': 'plant',
            'start_date': start, 'production_plan': json.dumps(PLAN), 'production_status': 'Growing', **extra}


class PlanningTests(unittest.TestCase):
    def test_staggered_without_stages_uses_maturity_and_has_no_stage_reminders(self):
        plan = validate_plan({'stages': [], 'interval_days': 14, 'reminder_days': 2,
                              'maturity_value': 6, 'maturity_unit': 'weeks'})
        result = schedule(plan, '2026-10-05')
        self.assertEqual(result['stages'], [])
        self.assertEqual(result['expected_harvest'], '2026-11-16')
        self.assertEqual(result['next_batch_start'], '2026-10-19')
        events = list(reminder_events([batch(production_plan=json.dumps(plan))], date(2026, 11, 17)))
        self.assertEqual({e[1] for e in events}, {'harvest', 'next-batch'})
        plan.update(maturity_value=1, maturity_unit='months')
        self.assertEqual(schedule(plan, '2028-01-31')['expected_harvest'], '2028-02-29')

    def test_six_week_maturity_two_week_stagger(self):
        plan = validate_plan(PLAN)
        a = schedule(plan, '2026-10-05')
        b = schedule(plan, a['next_batch_start'])
        self.assertEqual(a['next_batch_start'], '2026-10-19')
        self.assertEqual(a['expected_harvest'], '2026-11-16')
        self.assertEqual(b['expected_harvest'], '2026-11-30')
        self.assertEqual(a['stages'][1]['start_date'], '2026-10-12')

    def test_calendar_rollover_and_legacy(self):
        self.assertEqual(schedule(PLAN, '2027-12-25')['next_batch_start'], '2028-01-08')
        self.assertEqual(schedule(None, '2026-01-01'), {})
        self.assertEqual(validate_plan('{}'), {})

    def test_invalid_plans_rejected(self):
        for invalid in [dict(PLAN, stages=[]), dict(PLAN, interval_days=-1), dict(PLAN, reminder_days=14),
                        dict(PLAN, stages=[{'name': 'Leaf', 'days': 0}]),
                        dict(PLAN, stages=[{'name': 'Leaf', 'days': 1.5}]),
                        dict(PLAN, stages=[{'name': 'Leaf', 'days': 7}, {'name': ' leaf ', 'days': 7}])]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_plan(invalid)

    def test_next_start_replaced_by_new_batch_and_farm_independent(self):
        rows = [batch(), batch('b2', '2026-10-19'), batch('other-farm', farm='f2')]
        events = list(reminder_events(rows, date(2026, 10, 20)))
        starts = [event for event in events if event[1] == 'next-batch']
        self.assertEqual([event[0]['$id'] for event in starts], ['other-farm'])
        self.assertEqual(starts[0][4], 'overdue')

    def test_closed_batch_stops_stage_reminders_but_retains_next_start(self):
        events = list(reminder_events([batch(production_status='Completed')], date(2026, 11, 17)))
        self.assertEqual([e[1] for e in events], ['next-batch'])

    def test_new_legacy_batch_fulfills_old_start(self):
        events = reminder_events([batch(), batch('legacy', '2026-10-18', production_plan=None)], date(2026, 10, 20))
        self.assertFalse(any(e[1] == 'next-batch' for e in events))


class RouteTests(unittest.TestCase):
    def setUp(self):
        # Route tests must never fan out notifications through live Appwrite.
        notifications = patch('workflow_notifications.notify_change')
        notifications.start()
        self.addCleanup(notifications.stop)
        self.db = Mock()
        self.plant = {'$id': 'plant', 'name': 'Lettuce', 'production_plan': json.dumps(PLAN)}
        self.saved = batch()
        self.main = types.SimpleNamespace(db_id='db', db_collection_id1='users', db_collection_id2='farms',
            db_collection_id3='plants', db_collection_id5='batches', db_collection_id16='crops', bucket_id='bucket', project_id='project',
            appwrite_endpoint='https://example.test', db_collection_id25='notifications')
        def get(**kw):
            return {'plants': self.plant, 'farms': {'name': 'Farm', 'caretakerID': 'care'},
                    'users': {'name': 'Caretaker'}, 'batches': self.saved}[kw['collection_id']]
        self.db.get_document.side_effect = get
        self.db.create_document.side_effect = lambda **kw: {'$id': 'created', **kw['data']}
        self.db.update_document.side_effect = lambda **kw: {'$id': 'updated', **kw['data']}
        app = FastAPI()
        for path, name in [('r3_plant_type.py', 'collection3_router'), ('r5_batches.py', 'collection5_router')]:
            spec = importlib.util.spec_from_file_location('test_' + path[:-3], Path('routes') / path)
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {'main': self.main, 'db': types.SimpleNamespace(db=self.db),
                 'audit_utils': types.SimpleNamespace(write_audit=Mock()), 'storage': types.SimpleNamespace(st=Mock())}):
                spec.loader.exec_module(module)
            app.include_router(getattr(module, name))
            if hasattr(module, 'current_member'):
                app.dependency_overrides[module.current_member] = lambda: {'$id': 'manager', 'role': 'farm_manager'}
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_plant_validation_and_maturity_from_stages(self):
        payload = {'name': 'Lettuce', 'image_url': '', 'status': 'active', 'production_plan': json.dumps(PLAN)}
        response = self.client.post('/plant_type/info', data=payload)
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.db.create_document.call_args.kwargs['data']
        self.assertEqual(saved['maturity_max_value'], 42)
        self.assertEqual(saved['maturity_unit'], 'days')
        self.assertEqual(json.loads(saved['production_plan'])['interval_days'], 14)
        response = self.client.post('/plant_type/info', data={**payload, 'production_plan': '{bad'})
        self.assertEqual(response.status_code, 422)

    def test_staggered_plant_preserves_maturity_range_without_custom_stages(self):
        response = self.client.post('/plant_type/info', data={'name': 'Lettuce', 'status': 'active',
            'maturity_min_value': '4', 'maturity_max_value': '6', 'maturity_unit': 'weeks',
            'production_plan': json.dumps({'stages': [], 'interval_days': 14, 'reminder_days': 2})})
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.db.create_document.call_args.kwargs['data']
        self.assertEqual(saved['maturity_min_value'], 4)
        self.assertEqual(saved['maturity_max_value'], 6)
        self.assertEqual(saved['maturity_unit'], 'weeks')
        plan = json.loads(saved['production_plan'])
        self.assertEqual(plan['stages'], [])
        self.assertEqual(schedule(plan, '2026-10-05')['expected_harvest'], '2026-11-16')

    def test_batch_snapshots_plan_and_ignores_client_harvest_date(self):
        response = self.client.post('/batches/info', data={'batch_no': 'B1', 'farmID': 'farm', 'farm_name': 'Farm',
            'plant_type_ID': 'plant', 'plant_name': 'Lettuce', 'plant_variety': 'Green', 'farm_manager_id': 'manager',
            'farm_manager_name': 'Manager', 'start_date': '2026-10-05', 'end_date': '2026-10-06',
            'total_seeds_nursed': '100', 'created_by': 'manager'})
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.db.create_document.call_args.kwargs['data']
        self.assertEqual(saved['end_date'], '2026-11-16')
        self.assertEqual(json.loads(saved['production_plan'])['stages'], PLAN['stages'])

    def test_batch_edit_keeps_snapshot_after_catalog_changed(self):
        self.plant['production_plan'] = json.dumps({**PLAN, 'stages': [{'name': 'New', 'days': 90}]})
        response = self.client.put('/batches/b1', data={'start_date': '2026-10-19', 'end_date': '2026-10-20'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.update_document.call_args.kwargs['data']['end_date'], '2026-11-30')
        self.assertNotIn('production_plan', self.db.update_document.call_args.kwargs['data'])

    def test_reminders_scoped_and_deduplicated(self):
        from production_reminders import publish_reminders
        store = {'batches': [batch(start='2026-01-01')], 'farms': [{'$id': 'f1', 'caretakerID': 'care', 'farm_manager_id': 'manager'}],
            'users': [{'$id': 'care', 'role': 'caretaker', 'status': 'Active'}, {'$id': 'manager', 'role': 'farm_manager', 'status': 'Active'},
                      {'$id': 'admin', 'role': 'admin', 'status': 'Active'}, {'$id': 'super', 'role': 'superadmin', 'status': 'Active'},
                      {'$id': 'disabled', 'role': 'admin', 'status': 'Suspended'}, {'$id': 'stranger', 'role': 'caretaker', 'status': 'Active'}]}
        self.db.list_documents.side_effect = lambda **kw: {'documents': store[kw['collection_id']]}
        notifications = {}
        def create(**kw):
            key = kw['document_id']
            if key in notifications:
                raise AppwriteException('Duplicate', 409)
            notifications[key] = kw['data']
        self.db.create_document.side_effect = create
        with patch.dict(sys.modules, {'db': types.SimpleNamespace(db=self.db), 'main': self.main}):
            publish_reminders()
            count = len(notifications)
            publish_reminders()
        self.assertGreater(count, 0)
        self.assertEqual(count, len(notifications))
        self.assertEqual({n['recipient_id'] for n in notifications.values()}, {'care', 'manager', 'admin', 'super'})


if __name__ == '__main__':
    unittest.main()
