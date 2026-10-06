import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from farm_assignments import caretaker_ids, is_farm_caretaker, requested_caretakers, validate_new_caretakers
from workflow_notifications import events_for
from switch_control import can_control
from routes import r2_farms as farms, r24_farm_records as records


class FarmCaretakerTests(unittest.TestCase):
    def test_legacy_membership_and_removed_user(self):
        self.assertEqual(caretaker_ids({'caretakerID': 'a'}), ['a'])
        farm = {'caretakerID': 'a', 'caretaker_ids': ['a', 'b', 'b']}
        self.assertEqual(caretaker_ids(farm), ['a', 'b'])
        self.assertTrue(is_farm_caretaker(farm, {'$id': 'b'}))
        self.assertFalse(is_farm_caretaker(farm, {'$id': 'other'}))
        self.assertFalse(is_farm_caretaker({'caretakerID': 'a', 'caretaker_ids': ['b']}, {'$id': 'a'}))
        self.assertEqual(requested_caretakers(None, 'a', farm), ['a', 'b'])
        self.assertEqual(requested_caretakers('[]', 'a', farm), [])

    def test_validate_new_assignment_requires_active_caretaker_membership(self):
        user = {'role': 'technician', 'roles': ['technician', 'caretaker'], 'status': 'Active'}
        validate_new_caretakers(['b'], {}, lambda _: user)
        for invalid in [{**user, 'status': 'Suspended'}, {'role': 'admin', 'status': 'Active'}]:
            with self.assertRaises(HTTPException): validate_new_caretakers(['b'], {}, lambda _: invalid)
        for raw in ['{}', '[null]', '["Unassigned"]', 'oops']:
            with self.assertRaises(HTTPException): requested_caretakers(raw, '')

    def test_assignment_notifications_only_go_to_new_members(self):
        old = {'caretakerID': 'a', 'caretaker_ids': ['a', 'b'], 'name': 'Farm'}
        result = events_for('Farms', 'Update', old, {'caretaker_ids': ['a', 'b', 'c']})
        self.assertEqual(result[0]['recipients'], {'c'})
        self.assertEqual(events_for('Farms', 'Update', old, {'caretaker_ids': ['a']}), [])

    def test_each_caretaker_can_control_only_assigned_farm(self):
        farm = {'caretakerID': 'a', 'caretaker_ids': ['a', 'b']}
        for identity in ['a', 'b']:
            self.assertTrue(can_control({'$id': identity, 'role': 'caretaker', 'status': 'Active'}, farm))
        self.assertFalse(can_control({'$id': 'c', 'role': 'caretaker', 'status': 'Active'}, farm))


class AssignmentRouteTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'$id': 'admin', 'role': 'admin', 'status': 'Active'}
        self.farm = {'$id': 'farm', 'name': 'Farm', 'caretakerID': 'a', 'caretaker_ids': ['a', 'b']}
        app = FastAPI(); app.include_router(farms.collection2_router)
        app.dependency_overrides[farms.current_member] = lambda: self.actor
        self.client = TestClient(app)
        self.db = patch.object(farms, 'db').start(); patch.object(farms, 'write_audit').start()
        self.addCleanup(patch.stopall)
        self.db.get_document.side_effect = lambda *args, **kwargs: self.farm if kwargs or args[-1] == 'farm' else {'role': 'caretaker', 'status': 'Active'}
        self.db.update_document.side_effect = lambda **kwargs: {**self.farm, **kwargs['data']}
        self.data = dict(name='Farm', location='Accra', ownerID='owner', plant_type='Lettuce', plant_variety='Green', status='Active', tier_type='Compact', caretakerID='a')

    def test_legacy_status_update_preserves_entire_team(self):
        response = self.client.put('/farms/farm', data=self.data)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['user']['caretaker_ids'], ['a', 'b'])

    def test_removal_updates_legacy_primary_and_team_together(self):
        response = self.client.put('/farms/farm', data={**self.data, 'caretaker_ids': '["b","c"]'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['user']['caretakerID'], 'b')
        self.assertEqual(response.json()['user']['caretaker_ids'], ['b', 'c'])

    def test_non_admin_cannot_assign_farm_team(self):
        self.actor['role'] = 'caretaker'
        self.assertEqual(self.client.put('/farms/farm', data=self.data).status_code, 403)
        self.db.update_document.assert_not_called()


class SharedRecordTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'$id': 'b', 'name': 'Second caretaker', 'role': 'caretaker', 'status': 'Active'}
        self.farm = {'$id': 'farm', 'caretakerID': 'a', 'caretaker_ids': ['a', 'b']}
        self.batch = {'$id': 'batch', 'farmID': 'farm', 'caretaker_id': 'a', 'production_status': 'Growing', 'start_date': '2026-10-01'}
        app = FastAPI(); app.include_router(records.collection24_router)
        app.dependency_overrides[records.current_member] = lambda: self.actor
        self.client = TestClient(app)
        self.db = patch.object(records, 'db').start(); patch.object(records, 'write_audit').start()
        patch.object(records, 'queue_notification_email').start()
        self.addCleanup(patch.stopall)
        self.db.get_document.side_effect = lambda *args, **kwargs: self.batch if kwargs.get('document_id') == 'batch' else self.farm
        self.db.list_documents.return_value = {'documents': []}
        self.db.create_document.side_effect = lambda **kwargs: {'$id': 'record', **kwargs['data']}
        self.data = dict(farm_id='farm', farm_name='Farm', batch_id='batch', record_type='daily_monitoring', record_date='2026-10-06', created_by='spoofed', created_by_name='Other person', has_issues='false')

    def test_second_caretaker_records_existing_batch_with_verified_author(self):
        response = self.client.post('/farm-records/info', data=self.data)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['record']['created_by'], 'b')
        self.assertEqual(response.json()['record']['created_by_name'], 'Second caretaker')

    def test_removed_caretaker_is_denied_without_writes(self):
        self.farm['caretaker_ids'] = ['a']
        self.assertEqual(self.client.post('/farm-records/info', data=self.data).status_code, 403)
        self.db.create_document.assert_not_called()

    def test_completed_batch_stays_closed_for_all_caretakers(self):
        self.batch['production_status'] = 'Delivered'
        self.assertEqual(self.client.post('/farm-records/info', data=self.data).status_code, 409)
        self.db.create_document.assert_not_called()

    def test_server_calculates_stage_and_keeps_ph_ec_distinct(self):
        self.batch['production_plan'] = {'stages': [{'name': 'Sprouting', 'days': 3}, {'name': 'Leaf Development', 'days': 14}]}
        response = self.client.post('/farm-records/info', data={**self.data, 'growth_stage': 'Forged stage', 'ph': '6.2', 'ec': '1.5'})
        self.assertEqual(response.status_code, 200, response.text)
        record = response.json()['record']
        self.assertEqual(record['growth_stage'], 'Leaf Development')
        self.assertEqual(record['ph'], 6.2)
        self.assertEqual(record['ec'], 1.5)
