import json
import unittest
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from growing_groups import group_assignment, batch_record_view, batch_record_query
from routes import r24_farm_records as records
from routes import r5_batches as batches_route


class GroupAssignmentTests(unittest.TestCase):
    def test_join_requires_same_farm_and_authorized_role(self):
        farm = {'$id': 'f', 'farm_manager_id': 'manager'}
        member = {'farmID': 'f', 'growing_group_name': 'Room A'}
        actor = {'$id': 'manager', 'role': 'farm_manager'}
        self.assertEqual(group_assignment('g', '', farm, actor, lambda _: [member])['growing_group_name'], 'Room A')
        new = group_assignment('new', 'Room B', farm, actor, lambda _: [])
        self.assertEqual(len(new['growing_group_id']), 32)
        self.assertEqual(group_assignment('', '', farm, actor, lambda _: [])['growing_group_id'], '')
        for identity, role, members in [('g', 'caretaker', [member]), ('g', 'admin', [{**member, 'farmID': 'other'}]), ('g', 'admin', [])]:
            with self.assertRaises(HTTPException):
                group_assignment(identity, '', farm, {**actor, 'role': role}, lambda _: members)
        with self.assertRaises(HTTPException):
            group_assignment('new', 'Room', farm, actor, lambda _: [], {'production_status': 'Delivered'})

    def test_log_query_includes_shared_membership(self):
        query = json.loads(batch_record_query('b'))
        self.assertEqual(query['method'], 'or')
        self.assertEqual(len(query['values']), 2)


class GroupRecordTests(unittest.TestCase):
    def setUp(self):
        self.farm = {'$id': 'f', 'caretaker_ids': ['c']}
        self.batches = {identity: {'$id': identity, 'batch_no': identity.upper(), 'farmID': 'f',
            'growing_group_id': 'g', 'growing_group_name': 'System A', 'production_status': 'Growing',
            'start_date': start, 'production_plan': {'stages': [{'name': 'Sprouting', 'days': 3}, {'name': 'Leaf', 'days': 14}]}}
            for identity, start in [('a', '2026-10-01'), ('b', '2026-10-05')]}
        self.entries = [{'batch_id': 'a', 'observations': 'Yellow leaves', 'has_issues': True,
                         'issue_description': 'Yellowing', 'issue_severity': 'high'},
                        {'batch_id': 'b', 'observations': 'Healthy', 'has_issues': False}]
        self.data = dict(farm_id='f', farm_name='Farm', batch_id='a', record_type='watering',
                        record_date='2026-10-06', created_by='c', created_by_name='Care', has_issues='false',
                        ph='6.2', ec='1.5', water_bought_litres='100', water_bought_amount='25')
        app = FastAPI(); app.include_router(records.collection24_router)
        app.dependency_overrides[records.current_member] = lambda: {'$id': 'c', 'name': 'Care', 'role': 'caretaker'}
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.db = patch.object(records, 'db').start()
        patch.object(records, 'write_audit').start(); patch.object(records, 'queue_notification_email').start()
        self.addCleanup(patch.stopall)
        self.db.get_document.side_effect = lambda *args, **kwargs: self.batches.get(kwargs.get('document_id') or (args[-1] if args else ''), self.farm)
        self.db.list_documents.return_value = {'documents': []}
        self.db.create_document.side_effect = lambda **kwargs: {'$id': 'event', **kwargs['data']}

    def submit(self, **changes):
        return self.client.post('/farm-records/info', data={**self.data, 'batch_entries': json.dumps(self.entries), **changes})

    def test_one_event_individual_stages_issues_and_shared_water(self):
        response = self.submit()
        self.assertEqual(response.status_code, 200, response.text)
        record = response.json()['record']
        self.db.create_document.assert_called_once()
        self.db.update_document.assert_not_called()
        self.assertEqual(record['water_bought_litres'], 100)
        self.assertEqual(record['linked_batch_ids'], ['a', 'b'])
        a, b = batch_record_view(record, 'a'), batch_record_view(record, 'b')
        self.assertTrue(a['has_issues']); self.assertFalse(b['has_issues'])
        self.assertEqual(a['growth_stage'], 'Leaf'); self.assertEqual(b['growth_stage'], 'Sprouting')
        self.assertEqual(b['observations'], 'Healthy')
        self.assertEqual(a['ph'], b['ph'])
        self.assertNotIn('water_bought_amount', json.loads(record['batch_entries'])[0])

    def test_both_batches_can_have_distinct_issues(self):
        self.entries[1].update(has_issues=True, issue_description='Wilting', issue_severity='critical')
        record = self.submit().json()['record']
        self.assertEqual(record['issue_severity'], 'critical')
        self.assertEqual(batch_record_view(record, 'b')['issue_description'], 'Wilting')

    def test_cross_farm_unlinked_duplicate_and_changed_groups_rejected_before_write(self):
        for field, value in [('farmID', 'other'), ('growing_group_id', ''), ('growing_group_id', 'other')]:
            previous = self.batches['b'][field]; self.batches['b'][field] = value
            self.assertIn(self.submit().status_code, [403, 422])
            self.batches['b'][field] = previous
        self.entries[1]['batch_id'] = 'a'
        self.assertEqual(self.submit().status_code, 422)
        self.db.create_document.assert_not_called()


    def test_closed_future_and_progress_records_rejected(self):
        self.batches['b']['production_status'] = 'Delivered'
        self.assertEqual(self.submit().status_code, 409)
        self.batches['b']['production_status'] = 'Growing'
        self.assertEqual(self.submit(record_date='2026-10-02').status_code, 422)
        self.assertEqual(self.submit(record_type='harvesting').status_code, 422)
        self.assertEqual(self.submit(harvested_count='10').status_code, 422)
        self.entries[0]['issue_description'] = ''
        self.assertEqual(self.submit().status_code, 422)
        self.db.create_document.assert_not_called()


class GroupBatchRouteTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'$id': 'manager', 'role': 'farm_manager'}
        self.farm = {'$id': 'f', 'farm_manager_id': 'manager'}
        self.batch = {'$id': 'b', 'farmID': 'f', 'batch_no': 'B', 'growing_group_id': '', 'production_status': 'Growing'}
        app = FastAPI(); app.include_router(batches_route.collection5_router)
        app.dependency_overrides[batches_route.current_member] = lambda: self.actor
        self.client = TestClient(app); self.addCleanup(self.client.close)
        self.db = patch.object(batches_route, 'db').start(); patch.object(batches_route, 'write_audit').start()
        self.addCleanup(patch.stopall)
        self.db.get_document.side_effect = lambda *args, **kwargs: self.batch if kwargs else self.farm
        self.db.list_documents.return_value = {'documents': [{'farmID': 'f', 'growing_group_name': 'Room A'}]}
        self.db.update_document.side_effect = lambda **kwargs: {'$id': 'b', **kwargs['data']}

    def test_join_existing_and_unlink_keep_batch_identity(self):
        response = self.client.put('/batches/b', data={'growing_group_id': 'g'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['updated_data']['growing_group_name'], 'Room A')
        self.assertNotIn('batch_no', response.json()['updated_data'])
        self.batch['growing_group_id'] = 'g'
        response = self.client.put('/batches/b', data={'growing_group_id': 'individual'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['updated_data']['growing_group_id'], '')

    def test_unassigned_manager_cannot_link_batches(self):
        self.actor['$id'] = 'other'
        self.assertEqual(self.client.put('/batches/b', data={'growing_group_id': 'g'}).status_code, 403)
        self.db.update_document.assert_not_called()

    def test_closed_batch_preserves_existing_group_on_unrelated_edit(self):
        self.batch.update(growing_group_id='g', production_status='Completed')
        response = self.client.put('/batches/b', data={'growing_group_id': 'g', 'technical_issues': 'Notes'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('growing_group_id', response.json()['updated_data'])
        self.assertEqual(self.client.put('/batches/b', data={'growing_group_id': 'individual'}).status_code, 409)

