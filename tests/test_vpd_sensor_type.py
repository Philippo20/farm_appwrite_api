import unittest
from unittest.mock import Mock
from migrate_vpd_sensor_type import add_vpd


class VpdMigrationTests(unittest.TestCase):
    def test_preserves_existing_enum_values_and_is_repeatable(self):
        db = Mock()
        db.get_attribute.return_value = {'elements': ['temperature', 'humidity'],
                                         'required': True, 'default': None}
        self.assertTrue(add_vpd(db, 'database', 'sensors', 'sensortype'))
        self.assertEqual(db.update_enum_attribute.call_args.kwargs['elements'],
                         ['temperature', 'humidity', 'VPD'])
        db.get_attribute.return_value['elements'].append('VPD')
        self.assertFalse(add_vpd(db, 'database', 'sensors', 'sensortype'))
        self.assertEqual(db.update_enum_attribute.call_count, 1)
