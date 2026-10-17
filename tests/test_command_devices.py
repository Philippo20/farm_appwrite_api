import copy
import importlib.util
import json
from pathlib import Path
import sys
import threading
import types
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from device_commands import configured_commands, serialize_commands, config_revision
from sensor_capabilities import with_sensor_capabilities

CONFIG = [{'id': 'start', 'label': 'Start pump', 'value': 'PUMP_START'},
          {'id': 'stop', 'label': 'Stop pump', 'value': 'PUMP_STOP'}]

class CommandConfigTests(unittest.TestCase):
    def test_named_commands_are_validated_and_canonical(self):
        self.assertEqual(configured_commands(serialize_commands(CONFIG)), CONFIG)
        for raw in [None, 'bad json', [], [CONFIG[0]] * 2,
                    [{**CONFIG[0], 'value': ' ' }], [{**CONFIG[0], 'label': 'x' * 61}],
                    [{**CONFIG[0], 'value': 'x' * 257}], [{**CONFIG[0], 'value': 'ON\nOFF'}],
                    [{**CONFIG[0], 'unexpected': True}],
                    [CONFIG[0], {**CONFIG[1], 'label': 'start PUMP'}]]:
            with self.assertRaises(HTTPException): configured_commands(raw)
        capabilities = with_sensor_capabilities({'sensortype': 'command_device'})
        self.assertFalse(capabilities['maintenance_required'])
        self.assertFalse(capabilities['calibration_required'])

class CommandProtocolTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
        self.actor = {'$id': 'admin', 'role': 'admin', 'status': 'Active'}
        self.sensor = {'$id': 'device', 'farmID': 'farm', 'serial_number': 'F-001',
                       'sensortype': 'command_device', 'status': 'Active', 'command_config': serialize_commands(CONFIG)}
        self.farm = {'$id': 'farm', 'ownerID': 'owner', 'caretaker_ids': ['care'], 'technician_id': 'tech'}
        self.docs, self.kinds = {}, {}
        self.lock = threading.Lock()
        self.db, self.audit = Mock(), Mock()
        self.db.list_documents.return_value = {'documents': [self.sensor]}
        self.db.get_document.return_value = self.farm
        def read(identity):
            with self.lock: return copy.deepcopy(self.docs.get(identity))
        def write(identity, sensor_id, kind, payload, replace=False):
            with self.lock:
                if identity in self.docs and not replace: return False
                self.docs[identity] = copy.deepcopy(payload); self.kinds[identity] = kind
                return True
        self.read, self.write = read, write
        def auth_device(sensor, supplied):
            if supplied != 'farm-key': raise HTTPException(401, 'Invalid device key')
        def actor():
            if self.actor is None: raise HTTPException(401, 'Sign in')
            return self.actor
        main = types.SimpleNamespace(db_id='db', db_collection_id11='devices', db_collection_id2='farms')
        spec = importlib.util.spec_from_file_location('commands_under_test', Path('routes/command_devices.py'))
        self.route = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'main': main, 'db': types.SimpleNamespace(db=self.db),
            'audit_utils': types.SimpleNamespace(write_audit=self.audit),
            'routes.messaging': types.SimpleNamespace(current_member=actor),
            'routes.light_switches': types.SimpleNamespace(key=lambda kind, identity: kind + identity,
                get_doc=read, write_doc=write, authorize_device=auth_device, COLLECTION='controls')}):
            spec.loader.exec_module(self.route)
        self.patch_main = patch.dict(sys.modules, {'main': main}); self.patch_main.start(); self.addCleanup(self.patch_main.stop)
        patcher = patch.object(self.route, 'now_utc', side_effect=lambda: self.now); patcher.start(); self.addCleanup(patcher.stop)
        def latest(sensor):
            rows = [value for key, value in self.docs.items() if self.kinds[key] == 'device_command' and value['sensor_id'] == sensor]
            return copy.deepcopy(rows[-1]) if rows else None
        patcher = patch.object(self.route, 'latest', side_effect=latest); patcher.start(); self.addCleanup(patcher.stop)
        app = FastAPI(); app.include_router(self.route.router)
        self.client = TestClient(app); self.addCleanup(self.client.close)
        self.headers = {'x-sensor-key': 'farm-key'}

    def poll(self, sequence=0, session='boot-session-one', key='farm-key'):
        return self.client.post('/command-devices/F-001/poll',
            json={'session_id': session, 'sequence': sequence}, headers={'x-sensor-key': key})
    def send(self, command='start', request=None):
        return self.client.post('/command-devices/F-001/commands',
            json={'command_key': command, 'request_id': request or str(uuid4()), 'config_revision': config_revision(self.sensor)})
    def ack(self, request, success=True, sequence=0, session='boot-session-one', message='Pump started'):
        return self.client.post('/command-devices/F-001/ack', json={
            'session_id': session, 'sequence': sequence, 'command_id': request,
            'success': success, 'message': message}, headers=self.headers)
    def state(self): return self.client.get('/command-devices/F-001/state').json()

    def test_complete_board_flow_confirms_actual_result_and_opens_next_slot(self):
        self.assertFalse(self.state()['online'])
        self.assertIsNone(self.poll().json()['command'])
        request = str(uuid4()); sent = self.send(request=request)
        self.assertEqual(sent.status_code, 200, sent.text)
        self.assertEqual(sent.json()['last_command']['status'], 'pending')
        command = self.poll().json()['command']
        self.assertEqual(command['value'], 'PUMP_START')
        self.assertEqual(command['id'], request)
        self.assertEqual(self.ack(request).status_code, 200)
        self.assertEqual(self.state()['last_command']['status'], 'confirmed')
        self.assertEqual(self.state()['last_command']['result'], 'Pump started')
        self.assertTrue(self.poll().json()['advance_sequence'])
        self.poll(sequence=1)
        self.assertTrue(self.state()['ready'])
        self.assertEqual(self.send('stop').status_code, 200)
        self.assertEqual(self.audit.call_args.kwargs['performed_by_id'], 'admin')

    def test_presence_expires_after_grace_period_and_recovers_on_poll(self):
        self.poll()
        self.assertEqual(self.state()['offline_after_ms'], 5500)
        self.now += timedelta(seconds=5.499)
        self.assertTrue(self.state()['online'])
        self.now += timedelta(milliseconds=2)
        self.assertFalse(self.state()['online'])
        self.assertFalse(self.state()['ready'])
        self.assertEqual(self.send().status_code, 409)
        self.assertEqual(self.poll().status_code, 200)
        self.assertTrue(self.state()['online'])
        self.assertTrue(self.state()['ready'])

    def test_repeat_request_never_requeues_and_other_commands_cannot_overwrite_slot(self):
        self.poll(); request = str(uuid4())
        self.assertEqual(self.send(request=request).status_code, 200)
        self.assertEqual(self.send(request=request).status_code, 200)
        self.assertEqual(self.send('stop').status_code, 409)
        self.assertEqual(self.poll().json()['command']['value'], 'PUMP_START')
        self.assertEqual(self.send('stop', request=request).status_code, 409)
        self.ack(request); self.poll(sequence=1); self.send('stop')
        count = list(self.kinds.values()).count('device_command')
        self.send(request=request)
        self.assertEqual(list(self.kinds.values()).count('device_command'), count)

    def test_concurrent_senders_cannot_claim_the_same_board_slot(self):
        self.poll()
        def attempt(command):
            try:
                self.route.send('F-001', self.route.Send(command_key=command, request_id=uuid4(), config_revision=config_revision(self.sensor)), self.actor)
                return 200
            except HTTPException as error: return error.status_code
        with ThreadPoolExecutor(2) as pool: results = list(pool.map(attempt, ['start', 'stop']))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(list(self.kinds.values()).count('device_command'), 1)

    def test_offline_expired_and_inactive_devices_do_not_execute(self):
        self.assertEqual(self.send().status_code, 409)
        self.poll(); request = str(uuid4()); self.send(request=request)
        self.now += timedelta(seconds=10)
        self.assertEqual(self.state()['last_command']['status'], 'expired')
        response = self.poll().json()
        self.assertIsNone(response['command']); self.assertTrue(response['advance_sequence'])
        self.assertEqual(self.ack(request).status_code, 409)
        self.poll(sequence=1); self.now += timedelta(seconds=15.001)
        self.assertFalse(self.state()['online'])
        self.assertEqual(self.send().status_code, 409)
        self.poll(sequence=1); self.sensor['status'] = 'Inactive'
        self.assertEqual(self.send().status_code, 409)

    def test_restart_and_configuration_changes_discard_old_commands(self):
        self.poll(); request = str(uuid4()); self.send(request=request)
        self.sensor['command_config'] = serialize_commands([{**CONFIG[0], 'value': 'NEW_VALUE'}, CONFIG[1]])
        self.assertIsNone(self.poll().json()['command'])
        self.assertEqual(self.ack(request).status_code, 409)
        self.poll(session='new-boot-session')
        self.assertIsNone(self.poll(session='new-boot-session').json()['command'])
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.poll(session='new-boot-session').json()['command']['value'], 'NEW_VALUE')

    def test_only_configured_commands_and_authenticated_device_can_participate(self):
        self.assertEqual(self.poll(key='wrong').status_code, 401)
        self.assertFalse(self.state()['online'])
        self.poll()
        self.assertEqual(self.send('arbitrary-payload').status_code, 422)
        self.assertEqual(self.client.post('/command-devices/F-001/poll', json={
            'session_id': 'boot-session-one', 'sequence': True}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.post('/command-devices/F-001/commands', json={
            'command_key': 'start', 'request_id': 'invalid'}).status_code, 422)

    def test_failed_results_are_visible_and_cannot_be_rewritten(self):
        self.poll(); request = str(uuid4()); self.send(request=request)
        self.assertEqual(self.ack(request, False, message='Unknown value').status_code, 200)
        self.assertEqual(self.state()['last_command']['status'], 'failed')
        self.assertEqual(self.ack(request, False, message='Unknown value').status_code, 200)
        self.assertEqual(self.ack(request, True).status_code, 409)
        self.assertEqual(self.ack(request, sequence=9).status_code, 409)

    def test_a_stale_card_cannot_send_a_reconfigured_command_value(self):
        self.poll(); revision = config_revision(self.sensor)
        self.sensor['command_config'] = serialize_commands([{**CONFIG[0], 'value': 'NEW_VALUE'}])
        result = self.client.post('/command-devices/F-001/commands', json={
            'command_key': 'start', 'request_id': str(uuid4()), 'config_revision': revision})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(list(self.kinds.values()).count('device_command'), 0)

    def test_farm_scoping_and_technician_read_only_access(self):
        self.poll()
        for role, identity in [('caretaker', 'care'), ('farm_owner', 'owner'), ('superadmin', 'super')]:
            self.actor = {'$id': identity, 'role': role, 'status': 'Active'}
            self.assertEqual(self.client.get('/command-devices/F-001/state').status_code, 200)
            self.assertTrue(self.state()['can_send'])
        self.actor = {'$id': 'tech', 'role': 'technician', 'status': 'Active'}
        self.assertFalse(self.state()['can_send'])
        self.assertEqual(self.send().status_code, 403)
        self.actor = {'$id': 'other', 'role': 'caretaker', 'status': 'Active'}
        self.assertEqual(self.client.get('/command-devices/F-001/state').status_code, 403)
        self.actor = None
        self.assertEqual(self.send().status_code, 401)
