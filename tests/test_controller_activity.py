import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from appwrite.exception import AppwriteException
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from controller_activity import ControllerActivityEvent, ACTIVITY_TYPES, output_value, reported_elapsed
from equipment_links import reserve, release, guard_controller_change, validate_link, BINDINGS

def sample(generation=42, session='board-12345678-12345678', **changes):
    return {'event_id': f'{session}-{generation}', 'session_id': session, 'command_id': '',
        'type': 'controller.status', 'target': 'controller', 'uptime_ms': 120000,
        'rtc_unix_s': 1792674000, 'rtc_available': True, 'grid_available': True,
        'lights': {'pair': 'E+F', 'E': True, 'F': True, 'P': False, 'changing': False},
        'fertigation': {'enabled': {'E': True, 'F': True, 'P': True}, 'state': 'feeding',
            'active': True, 'pump_on': True, 'rack': 'E', 'source': 'scheduled',
            'manual_requested': False, 'configured_duration_ms': 120000,
            'started_uptime_ms': 118000, 'started_rtc_unix_s': 1792673998,
            'feeding': {'rack': 'E', 'started_uptime_ms': 119000, 'started_rtc_unix_s': 1792673999}},
        'drainage': {'ef': {'pump_on': False, 'tank_full': False, 'started_uptime_ms': None, 'started_rtc_unix_s': None},
            'p': {'pump_on': True, 'tank_full': True, 'started_uptime_ms': 110000, 'started_rtc_unix_s': 1792673990}}, **changes}

class ModelTests(unittest.TestCase):
    def test_full_v17_contract_and_numeric_generation(self):
        for kind in ACTIVITY_TYPES:
            event = ControllerActivityEvent(**sample(type=kind, reason='command_expired' if kind == 'command.rejected' else None))
            self.assertEqual(event.generation, 42)
            self.assertIsNone(event.command_id)
        self.assertGreater(ControllerActivityEvent(**sample(10)).generation, ControllerActivityEvent(**sample(2)).generation)

    def test_strict_validation(self):
        for changes in [{'grid_available': 'true'}, {'uptime_ms': True}, {'uptime_ms': -1}, {'type': 'unknown'},
            {'event_id': 'arbitrary-event'}, {'event_id': 'board-12345678-12345678-042'}, {'command_id': 'not-uuid'}, {'type': 'command.rejected'}]:
            with self.assertRaises(ValidationError): ControllerActivityEvent(**sample(**changes))
        bad = sample(); bad['lights']['E'] = 1
        with self.assertRaises(ValidationError): ControllerActivityEvent(**bad)

    def test_output_mapping_and_millisecond_wrap(self):
        state = sample()
        self.assertTrue(output_value(state, 'lights.E'))
        self.assertFalse(output_value(state, 'lights.P'))
        self.assertTrue(output_value(state, 'fertigation.pump_on'))
        self.assertFalse(output_value(state, 'drainage.ef.pump_on'))
        self.assertTrue(output_value(state, 'drainage.p.pump_on'))
        self.assertIsNone(output_value(state, 'missing.output'))
        self.assertEqual(reported_elapsed(state, 'fertigation.pump_on'), 1000)
        state['uptime_ms'] = 1000; state['drainage']['p']['started_uptime_ms'] = 4294967000
        self.assertEqual(reported_elapsed(state, 'drainage.p.pump_on'), 1296)

class ActivityRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock(); self.events = {}; self.heartbeat = None
        self.now = datetime.now(timezone.utc)
        self.sensor = {'$id': 'board', 'farmID': 'farm', 'sensortype': 'command_device', 'serial_number': 'CMD-001', 'status': 'Active'}
        self.authorize = Mock()
        def authorize_device(sensor, key):
            if key != 'farm-key': raise HTTPException(401, 'Bad key')
        self.db.create_document.side_effect = self.create
        self.db.get_document.side_effect = lambda database, collection, identity: self.events[identity]
        self.db.list_documents.side_effect = self.list
        self.module = types.ModuleType('activity_under_test')
        spec = importlib.util.spec_from_file_location(self.module.__name__, Path('routes/controller_activity.py'))
        with patch.dict(sys.modules, {'main': types.SimpleNamespace(db_id='db', db_collection_id11='devices', db_collection_id2='farms'),
            'db': types.SimpleNamespace(db=self.db),
            'routes.messaging': types.SimpleNamespace(current_member=lambda: {'role': 'admin'}),
            'routes.command_devices': types.SimpleNamespace(sensor_for=lambda serial: self.sensor, authorize=self.authorize, OFFLINE_SECONDS=5.5),
            'routes.light_switches': types.SimpleNamespace(authorize_device=authorize_device, get_doc=lambda identity: copy.deepcopy(self.heartbeat), key=lambda k,i: k+i)}):
            spec.loader.exec_module(self.module)
        self.module.now_utc = lambda: self.now
        app = FastAPI(); app.include_router(self.module.router)
        self.client = TestClient(app); self.addCleanup(self.client.close)

    def create(self, database, collection, identity, data, **kwargs):
        if identity in self.events: raise AppwriteException('duplicate', 409)
        self.events[identity] = {'$id': identity, **copy.deepcopy(data)}
        return self.events[identity]

    def list(self, database, collection, queries):
        rows = list(self.events.values())
        for raw in queries:
            q = json.loads(raw); kind = q['method']
            if kind == 'equal': rows = [r for r in rows if r.get(q['attribute']) in q['values']]
            if kind == 'orderDesc': rows.sort(key=lambda r: r[q['attribute']], reverse=True)
            if kind == 'limit': rows = rows[:q['values'][0]]
        return {'documents': rows}

    def ingest(self, body):
        return self.module.ingest_activity('CMD-001', ControllerActivityEvent(**body), 'farm-key')

    def test_duplicates_are_idempotent_and_conflicts_cannot_rewrite_history(self):
        body = sample()
        self.assertFalse(self.ingest(body)['duplicate'])
        self.assertTrue(self.ingest(body)['duplicate'])
        self.assertEqual(len(self.events), 1)
        with self.assertRaises(HTTPException) as error: self.ingest({**body, 'uptime_ms': 22})
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(next(iter(self.events.values()))['notification_pending'])

    def test_shared_event_endpoint_accepts_full_v17_payload(self):
        spec = importlib.util.spec_from_file_location('shared_events_under_test', Path('routes/calibration_events.py'))
        shared = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'main': types.SimpleNamespace(db_id='db'), 'db': types.SimpleNamespace(db=self.db),
            'routes.command_devices': types.SimpleNamespace(sensor_for=lambda serial: self.sensor, authorize=self.authorize),
            'routes.messaging': types.SimpleNamespace(current_member=lambda: {'role': 'admin'}),
            'routes.light_switches': types.SimpleNamespace(authorize_device=lambda *a: None, key=lambda k,i: k+i, get_doc=lambda identity: None, write_doc=Mock()),
            'workflow_notifications': types.SimpleNamespace(publish_event=Mock()),
            'routes.controller_activity': self.module}):
            spec.loader.exec_module(shared)
            app = FastAPI(); app.include_router(shared.router)
            with TestClient(app) as client:
                response = client.post('/command-devices/CMD-001/events', json=sample(), headers={'x-sensor-key': 'farm-key'})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()['accepted'])
                invalid = client.post('/command-devices/CMD-001/events', json=sample(grid_available='false'), headers={'x-sensor-key': 'farm-key'})
                self.assertEqual(invalid.status_code, 422)

    def test_late_delivery_cannot_replace_numeric_latest_or_revive_presence(self):
        self.heartbeat = {'session_id': sample()['session_id'], 'seen_at': self.now.isoformat()}
        self.ingest(sample(10)); self.ingest(sample(2))
        self.assertEqual(self.module.current_snapshot(self.sensor)['snapshot']['generation'], 10)
        self.now += timedelta(seconds=6)
        self.ingest(sample(11))
        self.assertFalse(self.module.current_snapshot(self.sensor)['online'])
        self.heartbeat = {'session_id': 'new-boot-session', 'seen_at': self.now.isoformat()}
        self.ingest(sample(99))
        state = self.module.current_snapshot(self.sensor)
        self.assertIsNone(state['snapshot']); self.assertTrue(state['online'])
        self.assertEqual(len(self.events), 4)

    def test_reboot_during_snapshot_query_invalidates_old_state(self):
        self.ingest(sample())
        self.heartbeat = {'session_id': sample()['session_id'], 'seen_at': self.now.isoformat()}
        previous = copy.deepcopy(self.heartbeat)
        self.module.get_doc = Mock(side_effect=[previous, {**previous, 'session_id': 'new-boot-session'}])
        self.assertIsNone(self.module.current_snapshot(self.sensor)['snapshot'])

    def test_faults_queue_notifications_but_not_normal_status(self):
        self.ingest(sample(1)); self.ingest(sample(2, type='grid.changed', grid_available=False))
        self.ingest(sample(3, type='rtc.changed', rtc_available=False))
        self.assertEqual(sum(e['notification_pending'] for e in self.events.values()), 2)
        # Acceptance only needs durable storage, not notification delivery.
        self.db.update_document.assert_not_called()

    def test_notification_outage_retries_independently_after_acceptance(self):
        self.ingest(sample(type='grid.changed', grid_available=False))
        self.db.get_document.side_effect = None; self.db.get_document.return_value = self.sensor
        publish = Mock(side_effect=RuntimeError('Temporary outage'))
        with patch.dict(sys.modules, {'workflow_notifications': types.SimpleNamespace(publish_event=publish, ADMIN_ROLES={'admin', 'superadmin'})}):
            with self.assertRaises(RuntimeError): self.module.publish_pending_notifications()
            self.db.update_document.assert_not_called()
            publish.side_effect = None
            self.module.publish_pending_notifications()
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(publish.call_args.args[1]['farm'], 'farm')
        self.db.update_document.assert_called_once()

    def test_farm_key_and_view_scope_are_enforced(self):
        with self.assertRaises(HTTPException): self.module.ingest_activity('CMD', ControllerActivityEvent(**sample()), 'wrong')
        self.db.create_document.assert_not_called()
        self.authorize.side_effect = HTTPException(403, 'Not assigned')
        self.assertEqual(self.client.get('/command-devices/CMD-001/activity').status_code, 403)

    def test_equipment_shares_one_controller_snapshot_and_real_maintenance_due(self):
        devices = [{'$id': 'light', 'farmID': 'farm', 'controller_id': 'board', 'controller_output': 'lights.E',
                    'maintenance_plan': '[]'},
                   {'$id': 'pump', 'farmID': 'farm', 'controller_id': 'board', 'controller_output': 'drainage.ef.pump_on',
                    'maintenance_plan': json.dumps([{'id': 'clean', 'type': 'cleaning', 'interval_days': 14, 'first_due': '2020-01-01'}])}]
        self.db.list_documents.side_effect = lambda *a, **kw: {'documents': devices}
        self.db.get_document.side_effect = None; self.db.get_document.return_value = self.sensor
        snapshot = self.module.current_snapshot = Mock(return_value={'snapshot': {**sample(), 'received_at': self.now.isoformat(), 'generation': 42},
            'online': True, 'seen_at': self.now.isoformat(), 'server_time': self.now.isoformat()})
        with patch.dict(sys.modules, {'routes.device_maintenance': types.SimpleNamespace(history_for=lambda identity: [])}):
            response = self.client.get('/controller-equipment?device_id=light&device_id=pump')
        self.assertEqual(response.status_code, 200, response.text)
        light, pump = response.json()['equipment']
        self.assertTrue(light['reported_on']); self.assertFalse(pump['reported_on'])
        self.assertEqual(light['maintenance_status'], 'No scheduled maintenance')
        self.assertEqual(pump['maintenance_status'], 'Overdue')
        snapshot.assert_called_once()

    def test_presence_only_skips_activity_and_maintenance_queries(self):
        devices = [{'$id': identity, 'farmID': 'farm', 'controller_id': 'board',
            'controller_output': output, 'maintenance_plan': '[{"id":"clean"}]'}
            for identity, output in [('light-e', 'lights.E'), ('light-f', 'lights.F')]]
        self.db.list_documents.side_effect = lambda *a, **kw: {'documents': devices}
        self.db.get_document.side_effect = None; self.db.get_document.return_value = self.sensor
        self.module.get_doc = Mock(return_value={'session_id': 'boot-session', 'seen_at': self.now.isoformat()})
        self.module.current_snapshot = Mock()
        history = Mock()
        with patch.dict(sys.modules, {'routes.device_maintenance': types.SimpleNamespace(history_for=history)}):
            response = self.client.get('/controller-equipment?device_id=light-e&device_id=light-f&presence_only=true')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertTrue(all(item['online'] for item in response.json()['equipment']))
        self.module.get_doc.assert_called_once()
        self.module.current_snapshot.assert_not_called(); history.assert_not_called()
        self.assertNotIn('maintenance_status', response.json()['equipment'][0])

    def test_compact_status_uses_each_output_without_maintenance_queries(self):
        devices = [{'$id': identity, 'farmID': 'farm', 'controller_id': 'board',
            'controller_output': output, 'maintenance_plan': '[{"id":"clean"}]'}
            for identity, output in [('light-e', 'lights.E'), ('light-f', 'lights.F')]]
        self.db.list_documents.side_effect = lambda *a, **kw: {'documents': devices}
        self.db.get_document.side_effect = None; self.db.get_document.return_value = self.sensor
        report = {**sample(), 'received_at': self.now.isoformat(), 'generation': 42}
        report['lights']['F'] = False
        snapshot = self.module.current_snapshot = Mock(return_value={'snapshot': report,
            'online': True, 'seen_at': self.now.isoformat(), 'server_time': self.now.isoformat()})
        history = Mock()
        with patch.dict(sys.modules, {'routes.device_maintenance': types.SimpleNamespace(history_for=history)}):
            response = self.client.get('/controller-equipment?device_id=light-e&device_id=light-f&status_only=true')
            self.assertEqual(response.status_code, 200, response.text)
            e, f = response.json()['equipment']
            self.assertTrue(e['online']); self.assertTrue(f['online'])
            self.assertTrue(e['reported_on']); self.assertFalse(f['reported_on'])
            snapshot.assert_called_once(); history.assert_not_called()
            self.assertNotIn('maintenance_status', e)
            # A fresh controller boot with no output report cannot invent ON.
            snapshot.return_value['snapshot'] = None
            response = self.client.get('/controller-equipment?device_id=light-e&device_id=light-f&status_only=true')
            self.assertTrue(all(item['reported_on'] is None for item in response.json()['equipment']))

class LinkTests(unittest.TestCase):
    def test_unique_claim_and_owner_checked_release(self):
        db = Mock(); db.create_document.side_effect = AppwriteException('duplicate', 409)
        db.get_document.return_value = {'device_id': 'existing'}
        with self.assertRaises(HTTPException) as error: reserve(db, 'db', 'board', 'lights.E', 'other')
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(reserve(db, 'db', 'board', 'lights.E', 'existing'))
        release(db, 'db', {'$id': 'other', 'controller_id': 'board', 'controller_output': 'lights.E'})
        db.delete_document.assert_not_called()
        release(db, 'db', {'$id': 'existing', 'controller_id': 'board', 'controller_output': 'lights.E'})
        db.delete_document.assert_called_once()

    def test_parent_farm_type_output_validation_and_delete_guard(self):
        db = Mock(); db.get_document.return_value = {'sensortype': 'command_device', 'farmID': 'farm'}
        validate_link(db, 'db', 'devices', 'grow_light', 'farm', 'board', 'lights.E')
        for kind, farm, output in [('grow_light', 'other', 'lights.E'), ('drainage_pump', 'farm', 'lights.E'), ('temperature', 'farm', 'lights.E')]:
            with self.assertRaises(HTTPException): validate_link(db, 'db', 'devices', kind, farm, 'board', output)
        db.list_documents.return_value = {'documents': [{'$id': 'light'}]}
        with self.assertRaises(HTTPException): guard_controller_change(db, 'db', 'devices', {'$id': 'board', 'sensortype': 'command_device'})

if __name__ == '__main__': unittest.main()
