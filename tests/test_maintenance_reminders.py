import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import maintenance_reminders as reminders


class MaintenanceReminderTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.now(timezone.utc).date()
        self.actor = {'$id': 'tech', 'role': 'technician', 'email': 'tech@example.com'}
        self.plan = {'id': 'plan', 'type': 'cleaning', 'interval_days': 14,
            'first_due': (self.today - timedelta(days=2)).isoformat(), 'assigned_to_id': 'tech'}
        self.device = {'$id': 'd', 'farmID': 'farm', 'model_number': 'Air conditioner',
                       'maintenance_plan': [self.plan]}
        self.history = []
        self.tasks = []
        self.app = FastAPI()
        self.app.include_router(reminders.router)
        self.app.dependency_overrides[reminders.actor_profile] = lambda: self.actor
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.available = {'farms': [{'$id': 'farm'}], 'devices': [self.device]}
        self.options = patch.object(reminders, 'options', side_effect=lambda _: self.available).start()
        self.rows = patch.object(reminders, 'rows', side_effect=lambda collection, queries=None:
            [{'payload': json.dumps(h)} for h in self.history] if collection == reminders.HISTORY else self.tasks).start()
        self.addCleanup(patch.stopall)

    def test_due_today_and_overdue_only_for_assigned_farms_and_user(self):
        def task(identity, days=0, **extra):
            return {'$id': identity, 'farm_id': 'farm', 'assigned_to_id': 'tech',
                'title': identity, 'status': 'Pending',
                'due_date': (self.today + timedelta(days=days)).isoformat(), **extra}
        self.tasks = [task('today'), task('late', -4), task('future', 1),
            task('completed', -5, status='Completed'), task('cancelled', -2, status='Cancelled'),
            task('someone-else', -1, assigned_to_id='other'), task('private-farm', -1, farm_id='other'),
            task('no-date', due_date=None)]
        data = self.client.get('/device-maintenance/due-reminders').json()
        self.assertEqual(data['count'], 3)
        self.assertEqual(data['overdue_count'], 2)
        self.assertEqual({item['title'] for item in data['items']}, {'today', 'late', 'Air conditioner: cleaning'})

    def test_completion_removes_reminder_but_other_work_stays(self):
        self.tasks = [{'farm_id': 'farm', 'title': 'Inspect tank', 'due_date': self.today.isoformat(), 'status': 'Pending'}]
        self.assertEqual(self.client.get('/device-maintenance/due-reminders').json()['count'], 2)
        self.history = [{'device_id': 'd', 'plan_id': 'plan', 'completed_on': self.today.isoformat()}]
        result = self.client.get('/device-maintenance/due-reminders').json()
        self.assertEqual(result['count'], 1)
        self.tasks[0]['status'] = 'Completed'
        self.assertEqual(self.client.get('/device-maintenance/due-reminders').json()['count'], 0)

    def test_foreign_plan_and_empty_assignments_never_show(self):
        self.plan['assigned_to_id'] = 'other'
        self.assertEqual(self.client.get('/device-maintenance/due-reminders').json()['count'], 0)
        self.rows.reset_mock()
        self.available['farms'] = []
        self.assertEqual(self.client.get('/device-maintenance/due-reminders').json()['count'], 0)
        self.rows.assert_not_called()
        self.actor['role'] = 'admin'
        self.assertEqual(self.client.get('/device-maintenance/due-reminders').status_code, 403)
