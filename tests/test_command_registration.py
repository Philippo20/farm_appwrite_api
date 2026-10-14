import json
import sys
import types
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests import test_device_maintenance as fixtures
from tests.test_command_devices import CONFIG

class CommandRegistrationTests(unittest.TestCase):
    list_documents = fixtures.MaintenanceRouteTests.list_documents
    create_document = fixtures.MaintenanceRouteTests.create_document
    update_document = fixtures.MaintenanceRouteTests.update_document
    def setUp(self):
        fixtures.MaintenanceRouteTests.setUp(self)
        self.profile['role'] = 'admin'
        patcher = patch.dict(sys.modules, {'routes.r11_sensors': self.sensors_module,
            'routes.messaging': types.SimpleNamespace(current_member=lambda *args: self.profile)})
        patcher.start(); self.addCleanup(patcher.stop)
        self.body = {'farmID': 'farm', 'sensortype': 'command_device', 'model_number': 'Pump controller',
                     'serial_number': 'CMD-001', 'location': 'Tank', 'command_config': json.dumps(CONFIG)}

    def test_register_persists_commands_and_has_no_reading_limits_or_calibration(self):
        response = self.client.post('/device-maintenance/devices', json={**self.body,
            'value': 123, 'unit': 'C', 'alerts_enabled': True, 'range_min': 1, 'range_max': 5})
        self.assertEqual(response.status_code, 200, response.text)
        device = response.json()['device']
        self.assertEqual(json.loads(device['command_config']), CONFIG)
        self.assertEqual(device['unit'], 'command')
        self.assertEqual(device['value'], 0)
        self.assertFalse(device['alerts_enabled'])
        self.assertIsNone(device['range_min'])
        self.assertEqual(device['maintenance_plan'], '[]')
        self.assertTrue(self.client.get('/device-maintenance/options').json()['can_configure_commands'])

    def test_technician_cannot_register_or_convert_command_device(self):
        self.profile['role'] = 'technician'
        self.assertFalse(self.client.get('/device-maintenance/options').json()['can_configure_commands'])
        self.assertEqual(self.client.post('/device-maintenance/devices', json=self.body).status_code, 403)
        self.device.update(sensortype='command_device', command_config=json.dumps(CONFIG))
        self.assertEqual(self.client.put('/device-maintenance/devices/device', json={**self.body,
            'sensortype': 'temperature', 'serial_number': 'F-001'}).status_code, 403)
        self.db.create_document.assert_not_called()

    def test_missing_or_invalid_configuration_never_creates_a_device(self):
        for value in [None, '', '[]', 'not json']:
            self.assertEqual(self.client.post('/device-maintenance/devices', json={**self.body,
                'command_config': value}).status_code, 422)
        self.db.create_document.assert_not_called()

    def test_existing_configuration_is_preserved_if_not_edited(self):
        self.device.update(sensortype='command_device', command_config=json.dumps(CONFIG))
        data = {key: value for key, value in self.body.items() if key != 'command_config'}
        data['serial_number'] = 'F-001'
        response = self.client.put('/device-maintenance/devices/device', json=data)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(json.loads(response.json()['device']['command_config']), CONFIG)

    def test_device_list_presence_comes_from_polls_not_registration_or_edit_time(self):
        sensor = {**self.device, 'sensortype': 'command_device', 'timestamp': '2026-10-14T12:00:00Z'}
        with patch.dict(sys.modules, {'routes.light_switches': types.SimpleNamespace(
            key=lambda kind, identity: kind + identity, get_doc=lambda identity: None)}):
            self.assertTrue(self.sensors_module._sensor_view(sensor)['timestamp'].startswith('1970'))
        with patch.dict(sys.modules, {'routes.light_switches': types.SimpleNamespace(
            key=lambda kind, identity: kind + identity, get_doc=lambda identity: {'seen_at': '2026-10-14T13:00:00Z'})}):
            self.assertEqual(self.sensors_module._sensor_view(sensor)['timestamp'], '2026-10-14T13:00:00Z')
        self.assertEqual(sensor['timestamp'], '2026-10-14T12:00:00Z')

    def test_legacy_management_paths_require_admin_and_ingest_cannot_write_commands(self):
        app = FastAPI(); app.include_router(self.sensors_module.collection11_router)
        client = TestClient(app); self.addCleanup(client.close)
        self.profile['role'] = 'technician'
        data = {**self.body, 'farm_name': 'Farm', 'status': 'Active', 'value': '0',
                'unit': 'command', 'alerts_enabled': 'false', 'timestamp': '2026-10-14T12:00:00Z'}
        self.assertEqual(client.post('/sensors/info', data=data).status_code, 403)
        self.assertEqual(client.post('/sensors/ingest', json={'serial_number': 'F-001',
            'sensortype': 'command_device', 'value': 0}).status_code, 422)
        self.db.create_document.assert_not_called()
