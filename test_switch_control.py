import unittest
from datetime import datetime, timedelta, timezone
from switch_control import online, command_live, can_control

class SwitchPoliciesTest(unittest.TestCase):
    def test_freshness_and_expiry(self):
        now = datetime.now(timezone.utc)
        heartbeat = {'seen_at': now.isoformat(), 'session_id': 'session-a'}
        command = {'expires_at': (now + timedelta(seconds=10)).isoformat(), 'session_id': 'session-a'}
        self.assertTrue(online(heartbeat, now + timedelta(seconds=15)))
        self.assertFalse(online(heartbeat, now + timedelta(seconds=15.001)))
        self.assertTrue(command_live(command, heartbeat, now))
        self.assertFalse(command_live(command, heartbeat, now + timedelta(seconds=10)))
        self.assertFalse(command_live(command, {**heartbeat, 'session_id': 'reconnected'}, now))
        self.assertFalse(online({'seen_at': 'bad'}, now))
    def test_access_scope(self):
        profile = {'$id': 'user-a', 'email': 'a@example.com', 'role': 'caretaker', 'status': 'Active'}
        self.assertTrue(can_control(profile, {'caretakerID': 'user-a'}))
        self.assertFalse(can_control(profile, {'caretakerID': 'user-b'}))
        self.assertFalse(can_control({**profile, 'status': 'Inactive'}, {'caretakerID': 'user-a'}))
        self.assertTrue(can_control({**profile, 'role': 'farm_owner'}, {'ownerID': 'user-a'}))
        self.assertFalse(can_control({**profile, 'role': 'sales_manager'}, {'ownerID': 'user-a'}))
        self.assertTrue(can_control({**profile, 'role': 'super_admin'}, {}))

if __name__ == '__main__': unittest.main()
