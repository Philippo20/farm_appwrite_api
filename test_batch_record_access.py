import unittest
from batch_record_access import can_review_records
class RecordAccessTests(unittest.TestCase):
    def test_roles_and_assignment(self):
        user = {'$id':'u1', 'email':'u1@example.com', 'role':'farm_manager', 'status':'Active'}
        self.assertTrue(can_review_records(user, {'farm_manager_id':'u1'}))
        self.assertTrue(can_review_records(user, {'farm_manager_id':'u1@example.com'}))
        self.assertFalse(can_review_records(user, {'farm_manager_id':'u2'}))
        self.assertFalse(can_review_records(user, {}))
        for role in ['admin', 'super_admin']:
            self.assertTrue(can_review_records({**user, 'role':role}, {}))
            self.assertFalse(can_review_records({**user, 'role':role, 'status':'Inactive'}, {}))
        self.assertFalse(can_review_records({**user, 'role':'caretaker'}, {'farm_manager_id':'u1'}))
if __name__ == '__main__': unittest.main()
