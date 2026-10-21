import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from datetime import timedelta
from uuid import uuid4
from unittest.mock import Mock, patch
from appwrite.exception import AppwriteException
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from calibration_events import CalibrationEvent, session_view, notification_for
from tests import test_command_devices as command_fixtures

def sample(**changes):
    return {'event_id': str(uuid4()), 'session_id': 'boot-session-one',
        'calibration_id': str(uuid4()), 'command_id': str(uuid4()),
        'type': 'calibration.running', 'target': 'ef_drain', 'state': 'running',
        'uptime_ms': 125000, 'elapsed_ms': 12400, 'saved': False, **changes}

class CalibrationModelTests(unittest.TestCase):
    def test_all_event_types_and_required_reasons_and_saved_measurements(self):
        for stage in ['request_received', 'waiting_for_start', 'starting', 'running',
                      'completed', 'cancelled', 'rejected', 'not_saved']:
            data = sample(type='calibration.' + stage)
            if stage in ['cancelled', 'rejected', 'not_saved']: data['reason'] = 'grid_power_lost'
            if stage == 'completed': data.update(saved=True, saved_duration_ms=12400)
            self.assertEqual(CalibrationEvent(**data).category, 'calibration')
        for data in [sample(type='calibration.cancelled'), sample(target='fertigation'),
            sample(rack='E'), sample(type='calibration.completed', saved=True),
            sample(saved=True, saved_duration_ms=123), sample(uptime_ms=True),
            sample(reason='unknown'), sample(category='other'), sample(rack='X'),
            sample(event_id='not-a-uuid'), sample(type='calibration.completed', saved=True, saved_duration_ms=0)]:
            with self.assertRaises(ValidationError): CalibrationEvent(**data)
        self.assertEqual(CalibrationEvent(**sample(target='fertigation', rack='P')).rack, 'P')

    def test_reordered_progress_never_overwrites_a_terminal_result(self):
        completed = sample(type='calibration.completed', saved=True, saved_duration_ms=1000,
            selection_at='2026-10-17T12:00:00Z', uptime_ms=100)
        late_progress = {**completed, 'type': 'calibration.running', 'uptime_ms': 200}
        for items in [[completed, late_progress], [late_progress, completed]]:
            self.assertEqual(session_view(items)['status'], 'completed')

    def test_a_rejected_repeat_does_not_claim_that_the_pump_stopped(self):
        running = sample(selection_at='2026-10-17T12:00:00Z')
        rejected = {**running, 'event_id': str(uuid4()), 'type': 'calibration.rejected',
                    'uptime_ms': 125001, 'reason': 'calibration_already_running'}
        self.assertEqual(session_view([running, rejected])['status'], 'running')
        self.assertEqual(session_view([running, rejected])['latest_event']['type'], 'calibration.rejected')

    def test_rejected_start_retains_the_last_confirmed_ready_stage(self):
        ready = sample(type='calibration.waiting_for_start', selection_at='2026-10-17T12:00:00Z')
        rejected = {**ready, 'event_id': str(uuid4()), 'type': 'calibration.rejected',
            'uptime_ms': 125001, 'reason': 'grid_power_unavailable'}
        view = session_view([ready, rejected])
        self.assertEqual(view['status'], 'rejected')
        self.assertEqual(view['last_progress']['type'], 'calibration.waiting_for_start')

    def test_only_meaningful_outcomes_publish_notifications(self):
        sensor = {'serial_number': 'CMD', 'farmID': 'farm'}
        self.assertIsNone(notification_for(sample(), sensor, 'admin'))
        event = notification_for(sample(type='calibration.not_saved', reason='duration_too_short'), sensor, 'admin')
        self.assertEqual(event['farm'], 'farm')
        self.assertEqual(event['recipients'], {'admin'})

    def test_notification_retry_is_private_and_does_not_repeat_push(self):
        from workflow_notifications import publish_event
        fake = Mock(); notifications = {}; push = Mock()
        users = [{'$id': identity, 'role': role, 'status': 'Active', 'name': identity}
                 for identity, role in [('admin', 'admin'), ('tech', 'technician'),
                                        ('care', 'caretaker'), ('stranger', 'caretaker')]]
        fake.list_documents.return_value = {'documents': users}
        fake.get_document.return_value = {'technician_id': 'tech', 'caretaker_ids': ['care']}
        def create(**kwargs):
            identity = kwargs['document_id']
            if identity in notifications: raise AppwriteException('duplicate', 409)
            notifications[identity] = kwargs['data']
        fake.create_document.side_effect = create
        notice = notification_for(sample(type='calibration.cancelled', reason='grid_power_lost'),
                                  {'serial_number': 'CMD', 'farmID': 'farm'}, 'admin')
        with patch.dict(sys.modules, {'db': types.SimpleNamespace(db=fake),
            'main': types.SimpleNamespace(db_id='db', db_collection_id1='users',
                db_collection_id2='farms', db_collection_id25='notifications'),
            'push_notifications': types.SimpleNamespace(queue_push=push)}):
            publish_event('calibration:one-event', notice)
            publish_event('calibration:one-event', notice)
        self.assertEqual({row['recipient_id'] for row in notifications.values()}, {'admin', 'tech', 'care'})
        self.assertEqual(push.call_count, 3)

class CalibrationRouteTests(unittest.TestCase):
    poll = command_fixtures.CommandProtocolTests.poll
    send = command_fixtures.CommandProtocolTests.send
    ack = command_fixtures.CommandProtocolTests.ack
    state = command_fixtures.CommandProtocolTests.state
    def setUp(self):
        command_fixtures.CommandProtocolTests.setUp(self)
        self.event_docs = {}
        self.publish = Mock()
        self.db.create_document.side_effect = self.create_event
        self.db.get_document.side_effect = self.get_event
        self.db.list_documents.side_effect = self.list_events
        spec = importlib.util.spec_from_file_location('calibration_route_under_test', Path('routes/calibration_events.py'))
        self.cal = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'main': types.SimpleNamespace(db_id='db'),
            'db': types.SimpleNamespace(db=self.db), 'routes.command_devices': self.route,
            'routes.messaging': types.SimpleNamespace(current_member=lambda: self.actor),
            'routes.light_switches': types.SimpleNamespace(key=self.route.key, get_doc=self.read,
                write_doc=self.write, authorize_device=self.route.authorize_device),
            'workflow_notifications': types.SimpleNamespace(publish_event=self.publish)}):
            spec.loader.exec_module(self.cal)
        patcher = patch.object(self.cal, 'now_utc', side_effect=lambda: self.now)
        patcher.start(); self.addCleanup(patcher.stop)
        app = FastAPI(); app.include_router(self.cal.router)
        self.events_client = TestClient(app); self.addCleanup(self.events_client.close)
        self.poll()
        self.selection = str(uuid4()); self.send(request=self.selection)
        self.body = sample(calibration_id=self.selection, command_id=self.selection)

    def create_event(self, database, collection, identity, data, **kwargs):
        if identity in self.event_docs: raise AppwriteException('duplicate', 409)
        self.event_docs[identity] = {'$id': identity, **copy.deepcopy(data)}
        return self.event_docs[identity]

    def get_event(self, database, collection, identity):
        if collection != self.cal.COLLECTION: return self.farm
        if identity not in self.event_docs: raise AppwriteException('missing', 404)
        return copy.deepcopy(self.event_docs[identity])

    def list_events(self, database, collection, queries=None):
        if collection != self.cal.COLLECTION: return {'documents': [self.sensor]}
        rows = list(self.event_docs.values()); orders = []; limit = 100; cursor = None
        for raw in queries or []:
            query = json.loads(raw); method = query['method']; values = query.get('values', [])
            if method == 'equal': rows = [row for row in rows if row.get(query['attribute']) in values]
            elif method == 'orderDesc': orders.append(query['attribute'])
            elif method == 'limit': limit = values[0]
            elif method == 'cursorAfter': cursor = values[0]
        for field in reversed(orders): rows.sort(key=lambda row: row[field], reverse=True)
        if cursor: rows = rows[next(i + 1 for i, row in enumerate(rows) if row['$id'] == cursor):]
        return {'documents': copy.deepcopy(rows[:limit])}

    def post(self, body=None, key='farm-key'):
        return self.events_client.post('/command-devices/F-001/events', json=body or self.body,
            headers={'x-sensor-key': key})
    def overview(self): return self.events_client.get('/command-devices/F-001/calibrations')

    def test_device_without_events_needs_only_one_event_query(self):
        with patch.object(self.cal, 'rows_for', wraps=self.cal.rows_for) as queries:
            response = self.overview()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['current'])
        self.assertEqual(response.json()['saved_durations'], [])
        self.assertEqual(queries.call_count, 1)

    def test_event_is_persistent_idempotent_and_does_not_renew_heartbeat(self):
        heartbeat = self.read(self.route.key('j', 'device'))
        self.now += timedelta(minutes=5)
        self.assertEqual(self.post().status_code, 200)
        retry = self.post()
        self.assertTrue(retry.json()['duplicate'])
        self.assertEqual(len(self.event_docs), 1)
        self.assertEqual(self.read(self.route.key('j', 'device')), heartbeat)
        self.assertFalse(self.state()['online'])
        self.assertEqual(self.overview().json()['current']['status'], 'running')
        self.publish.assert_not_called()

    def test_event_id_conflicts_and_device_keys_and_targets_are_enforced(self):
        self.assertEqual(self.post(key='wrong').status_code, 401)
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post({**self.body, 'message': 'changed'}).status_code, 409)
        self.assertEqual(self.post({**self.body, 'event_id': str(uuid4()), 'target': 'p_drain'}).status_code, 409)
        self.assertEqual(self.post({**self.body, 'calibration_id': str(uuid4())}).status_code, 409)
        self.assertEqual(self.post({**self.body, 'session_id': 'different-boot'}).status_code, 409)
        self.assertEqual(len(self.event_docs), 1)

    def test_a_calibration_cannot_publish_conflicting_final_results(self):
        complete = {**self.body, 'type': 'calibration.completed', 'saved': True, 'saved_duration_ms': 1000}
        self.assertEqual(self.post(complete).status_code, 200)
        conflict = {**self.body, 'event_id': str(uuid4()), 'type': 'calibration.cancelled', 'reason': 'user_cancelled'}
        self.assertEqual(self.post(conflict).status_code, 409)
        self.assertEqual(self.overview().json()['current']['status'], 'completed')

    def test_out_of_order_completion_and_cancellation_retain_saved_duration(self):
        completed = {**self.body, 'type': 'calibration.completed', 'saved': True,
                     'saved_duration_ms': 12400}
        self.assertEqual(self.post(completed).status_code, 200)
        self.post({**self.body, 'event_id': str(uuid4()), 'uptime_ms': 120000})
        result = self.overview().json()
        self.assertEqual(result['current']['status'], 'completed')
        self.assertEqual(result['saved_durations'][0]['saved_duration_ms'], 12400)
        self.ack(self.selection); self.poll(sequence=1); self.now += timedelta(seconds=1)
        next_id = str(uuid4()); self.send(request=next_id)
        self.post({**self.body, 'event_id': str(uuid4()), 'calibration_id': next_id,
            'command_id': next_id, 'type': 'calibration.cancelled', 'reason': 'user_cancelled'})
        result = self.overview().json()
        self.assertEqual(result['current']['status'], 'cancelled')
        self.assertEqual(result['saved_durations'][0]['saved_duration_ms'], 12400)
        # A delayed historical event cannot replace the newer calibration.
        self.post({**self.body, 'event_id': str(uuid4()), 'type': 'calibration.waiting_for_start'})
        self.assertEqual(self.overview().json()['current']['calibration_id'], next_id)

    def test_terminal_notification_delivery_can_retry_without_reinserting_event(self):
        self.publish.side_effect = [RuntimeError('temporary notification outage'), None]
        body = {**self.body, 'type': 'calibration.not_saved', 'reason': 'duration_too_short'}
        self.assertEqual(self.post(body).status_code, 503)
        retry = self.post(body)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()['duplicate'])
        self.assertEqual(len(self.event_docs), 1)
        self.assertEqual(self.publish.call_args_list[0].args[0], self.publish.call_args_list[1].args[0])

    def test_queued_previous_boot_events_are_accepted_without_resurrecting_presence(self):
        self.poll(session='new-boot-session')
        self.now += timedelta(seconds=10)
        self.assertEqual(self.post().status_code, 200)
        self.assertFalse(self.state()['online'])

    def test_farm_access_and_history_pagination(self):
        for index in range(3): self.post({**self.body, 'event_id': str(uuid4()), 'uptime_ms': 1000 + index})
        page = self.events_client.get('/command-devices/F-001/calibrations/events?limit=2').json()
        self.assertEqual(len(page['events']), 2)
        next_page = self.events_client.get('/command-devices/F-001/calibrations/events', params={'before': page['next_cursor'], 'limit': 2}).json()
        self.assertEqual(len(next_page['events']), 1)
        self.assertNotEqual(page['events'][0]['event_id'], next_page['events'][0]['event_id'])
        wrong_filter = self.events_client.get('/command-devices/F-001/calibrations/events',
            params={'before': page['next_cursor'], 'calibration_id': str(uuid4())})
        self.assertEqual(wrong_filter.status_code, 404)
        self.actor = {'$id': 'stranger', 'role': 'caretaker', 'status': 'Active'}
        self.assertEqual(self.overview().status_code, 403)

    def test_fertigation_saved_measurements_are_independent_per_rack(self):
        current = self.selection
        for index, rack in enumerate(['E', 'F', 'P']):
            if index:
                self.ack(current, sequence=index - 1)
                self.poll(sequence=index); self.now += timedelta(milliseconds=1)
                current = str(uuid4()); self.send(request=current)
            response = self.post({**self.body, 'event_id': str(uuid4()),
                'calibration_id': current, 'command_id': current, 'target': 'fertigation',
                'rack': rack, 'type': 'calibration.completed', 'saved': True,
                'saved_duration_ms': (index + 1) * 1000})
            self.assertEqual(response.status_code, 200, response.text)
        saved = self.overview().json()['saved_durations']
        self.assertEqual({e['rack']: e['saved_duration_ms'] for e in saved}, {'E': 1000, 'F': 2000, 'P': 3000})
