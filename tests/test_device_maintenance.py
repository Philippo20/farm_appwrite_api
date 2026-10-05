import importlib.util
import json
import sys
import types
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from appwrite.exception import AppwriteException
from device_maintenance import can_manage, schedule_view, occurrence_id

class MaintenancePolicyTests(unittest.TestCase):
    def test_tasks_independent_and_next_due_uses_completion(self):
        device = {'$id': 'device', 'farmID': 'farm'}
        cleaning = {'id': 'clean', 'type': 'cleaning', 'interval_days': 7, 'first_due': '2026-01-01'}
        calibration = {'id': 'cal', 'type': 'calibration', 'interval_days': 30, 'first_due': '2026-01-02'}
        history = [{'plan_id': 'clean', 'completed_on': '2026-01-03'}]
        clean = schedule_view(device, cleaning, history, date(2026, 1, 3))
        cal = schedule_view(device, calibration, history, date(2026, 1, 3))
        self.assertEqual(clean['due_date'], '2026-01-10')
        self.assertEqual(clean['status'], 'Due soon')
        self.assertEqual(cal['due_date'], '2026-01-02')
        self.assertEqual(cal['status'], 'Overdue')

    def test_access_fails_closed_and_allows_assigned_technicians(self):
        farm = {'$id': 'farm', 'technician_id': 'tech'}
        self.assertTrue(can_manage({'$id': 'tech', 'role': 'technician', 'status': 'Active'}, farm))
        self.assertFalse(can_manage({'$id': 'other', 'role': 'technician', 'status': 'Active'}, farm))
        self.assertFalse(can_manage({'$id': 'tech', 'role': 'technician', 'status': 'Suspended'}, farm))
        self.assertTrue(can_manage({'role': 'admin', 'status': 'Active'}, farm))
        self.assertTrue(can_manage({'role': 'technician', 'status': 'Active', 'assigned_farm_ids': ['farm']}, farm))

    def test_occurrence_key_is_stable_and_plan_specific(self):
        self.assertEqual(occurrence_id('d', 'p', '2026-01-01'), occurrence_id('d', 'p', '2026-01-01'))
        self.assertNotEqual(occurrence_id('d', 'p', '2026-01-01'), occurrence_id('d', 'q', '2026-01-01'))

class MaintenanceRouteTests(unittest.TestCase):
    def setUp(self):
        self.profile = {'$id': 'tech', 'role': 'technician', 'status': 'Active', 'name': 'Technician'}
        self.farm = {'$id': 'farm', 'technician_id': 'tech', 'name': 'Farm'}
        self.plan = {'id': 'plan', 'type': 'calibration', 'interval_days': 30, 'first_due': '2026-01-01', 'assigned_to_id': 'tech'}
        self.device = {'$id': 'device', 'farmID': 'farm', 'farm_name': 'Farm', 'serial_number': 'F-001',
                       'sensortype': 'pH Level', 'model_number': 'pH sensor', 'maintenance_plan': json.dumps([self.plan])}
        self.store = {'farms': {'farm': self.farm}, 'devices': {'device': self.device}, 'users': {'tech': self.profile}, 'device_maintenance_history': {}}
        self.db = Mock()
        self.db.get_document.side_effect = lambda database, collection, identity: self.store[collection][identity]
        self.db.list_documents.side_effect = self.list_documents
        self.db.create_document.side_effect = self.create_document
        main = types.ModuleType('main')
        for key, value in {'db_id': 'db', 'db_collection_id1': 'users', 'db_collection_id2': 'farms', 'db_collection_id11': 'devices', 'db_collection_id18': 'config', 'db_collection_id21': 'readings'}.items(): setattr(main, key, value)
        spec = importlib.util.spec_from_file_location('maintenance_under_test', Path('routes/device_maintenance.py'))
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'main': main, 'db': types.SimpleNamespace(db=self.db),
                                     'auth': types.SimpleNamespace(get_current_user=lambda: {'email': 'tech@test.com'})}):
            spec.loader.exec_module(self.module)
        sensor_spec = importlib.util.spec_from_file_location('sensor_routes_under_test', Path('routes/r11_sensors.py'))
        self.sensors_module = importlib.util.module_from_spec(sensor_spec)
        with patch.dict(sys.modules, {'main': main, 'db': types.SimpleNamespace(db=self.db)}):
            sensor_spec.loader.exec_module(self.sensors_module)
        self.db.update_document.side_effect = self.update_document
        app = FastAPI()
        app.include_router(self.module.router)
        app.dependency_overrides[self.module.actor_profile] = lambda: self.profile
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.payload = {'due_date': '2026-01-01', 'completed_on': date.today().isoformat(),
                        'work_performed': 'Cleaned and calibrated using reference solutions', 'calibration_results': 'Reference readings verified', 'follow_up': ''}

    def list_documents(self, database, collection, queries=None):
        records = list(self.store[collection].values())
        for raw in queries or []:
            query = json.loads(raw)
            if query['method'] == 'equal': records = [row for row in records if row.get(query['attribute']) in query['values']]
            if query['method'] == 'offset': records = records[query['values'][0]:]
            if query['method'] == 'limit': records = records[:query['values'][0]]
        return {'documents': records, 'total': len(records)}

    def create_document(self, database, collection, identity, data, **kwargs):
        if identity in self.store[collection]: raise AppwriteException('Conflict', 409)
        self.store[collection][identity] = {'$id': identity, **data}
        return self.store[collection][identity]

    def update_document(self, database, collection, identity, data, **kwargs):
        self.store[collection][identity].update(data)
        return self.store[collection][identity]

    def test_register_equipment_and_edit_preserves_reading_and_plan_id(self):
        body = {'farmID': 'farm', 'sensortype': 'air_conditioner', 'model_number': 'AC unit',
                'location': 'Grow room', 'serial_number': 'AC-001', 'unit': 'equipment',
                'plans': [{'type': 'cleaning', 'interval_days': 14, 'first_due': '2026-01-01'}]}
        with patch.dict(sys.modules, {'routes.r11_sensors': self.sensors_module}):
            response = self.client.post('/device-maintenance/devices', json=body)
            self.assertEqual(response.status_code, 200, response.text)
            saved = response.json()['device']
            plans = json.loads(saved['maintenance_plan'])
            self.assertEqual(plans[0]['type'], 'cleaning')
            self.assertEqual(saved['maintenance_frequency'], 'Per task')
            self.assertEqual(plans[0]['assigned_to_id'], 'tech')
            self.store['devices'][saved['$id']]['value'] = 17
            response = self.client.put('/device-maintenance/devices/' + saved['$id'], json={**body, 'plans': plans, 'value': 99})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['device']['value'], 17)
            self.assertEqual(json.loads(response.json()['device']['maintenance_plan'])[0]['id'], plans[0]['id'])
            duplicate = self.client.post('/device-maintenance/devices', json=body)
            self.assertEqual(duplicate.status_code, 409)

    def test_invalid_thresholds_and_foreign_device_edits_rejected(self):
        body = {'farmID': 'farm', 'sensortype': 'pH Level', 'model_number': 'pH', 'location': 'Tank',
                'range_min': 10, 'range_max': 5, 'plans': []}
        with patch.dict(sys.modules, {'routes.r11_sensors': self.sensors_module}):
            self.assertEqual(self.client.post('/device-maintenance/devices', json=body).status_code, 422)
            self.profile['$id'] = 'other'
            self.assertEqual(self.client.put('/device-maintenance/devices/device', json=body).status_code, 403)
        self.db.create_document.assert_not_called()

    def test_complete_saves_real_record_and_next_date_without_changing_telemetry(self):
        response = self.client.post('/device-maintenance/devices/device/plans/plan/complete', json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['next_task']['due_date'], (date.today() + timedelta(days=30)).isoformat())
        self.assertEqual(len(self.store['device_maintenance_history']), 1)
        self.db.update_document.assert_not_called()
        duplicate = self.client.post('/device-maintenance/devices/device/plans/plan/complete', json=self.payload)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(len(self.store['device_maintenance_history']), 1)

    def test_history_survives_device_removal(self):
        self.assertEqual(self.client.post('/device-maintenance/devices/device/plans/plan/complete', json=self.payload).status_code, 200)
        del self.store['devices']['device']
        response = self.client.get('/device-maintenance/overview')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tasks'], [])
        self.assertEqual(len(response.json()['history']), 1)

    def test_calibration_requires_results_and_no_future_completion(self):
        for override in [{'calibration_results': ''}, {'completed_on': (date.today() + timedelta(days=1)).isoformat()}]:
            response = self.client.post('/device-maintenance/devices/device/plans/plan/complete', json={**self.payload, **override})
            self.assertEqual(response.status_code, 422)
        self.db.create_document.assert_not_called()

    def test_unassigned_technician_cannot_read_or_complete_other_farm(self):
        self.profile['$id'] = 'other'
        response = self.client.get('/device-maintenance/overview')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tasks'], [])
        response = self.client.post('/device-maintenance/devices/device/plans/plan/complete', json=self.payload)
        self.assertEqual(response.status_code, 403)
        self.db.create_document.assert_not_called()

    def test_old_devices_without_plans_remain_visible_and_not_auto_scheduled(self):
        self.device.pop('maintenance_plan')
        response = self.client.get('/device-maintenance/overview')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['devices']), 1)
        self.assertEqual(response.json()['tasks'], [])

    def test_duplicate_types_and_foreign_plan_ids_are_rejected(self):
        Plan = self.module.Plan
        plan = Plan(type='cleaning', interval_days=7, first_due=date.today())
        for submitted in [[plan, plan], [Plan(id='foreign', type='cleaning', interval_days=7, first_due=date.today())]]:
            with self.assertRaises(Exception) as error:
                self.module.prepare_plans(submitted, self.device, self.profile, self.farm)
            self.assertEqual(error.exception.status_code, 422)

    def test_completion_conflict_is_not_success_or_overwrite(self):
        self.db.create_document.side_effect = AppwriteException('Conflict', 409)
        response = self.client.post('/device-maintenance/devices/device/plans/plan/complete', json=self.payload)
        self.assertEqual(response.status_code, 409)
        self.db.update_document.assert_not_called()

if __name__ == '__main__': unittest.main()
