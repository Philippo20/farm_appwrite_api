import unittest
from sensor_capabilities import sensor_calibration_required, with_sensor_capabilities

class SensorCapabilitiesTest(unittest.TestCase):
    def test_type_defaults(self):
        self.assertIs(sensor_calibration_required({'sensortype': 'Temperature'}), False)
        for kind in ['pH Level', 'EC Level', 'TDS', 'conductivity']:
            self.assertIs(sensor_calibration_required({'sensortype': kind}), True)
        self.assertIsNone(sensor_calibration_required({'sensortype': 'humidity'}))

    def test_override_and_non_mutating_response(self):
        original = {'sensortype': 'temperature', 'calibration_required': True}
        self.assertTrue(with_sensor_capabilities(original)['calibration_required'])
        sensor = {'sensortype': 'temperature', '$id': 'abc'}
        self.assertFalse(with_sensor_capabilities(sensor)['calibration_required'])
        self.assertNotIn('calibration_required', sensor)

class MaintenancePolicyTests(unittest.TestCase):
    def test_environment_sensors_do_not_require_maintenance(self):
        from sensor_capabilities import sensor_maintenance_required, maintenance_values
        for kind in ['temperature', 'Humidity', 'VPD', 'light', 'Carbon Dioxide', 'CO₂', 'Light Intensity', 'Relative Humidity']:
            self.assertFalse(sensor_maintenance_required({'sensortype': kind}), kind)
            self.assertEqual(maintenance_values(kind, 'Monthly', '2026-01-01'), {'maintenance_frequency': 'Not required', 'last_maintenance_date': None})

    def test_other_types_keep_required_maintenance(self):
        from sensor_capabilities import maintenance_values, sensor_maintenance_required
        for kind in ['pH Level', 'EC Level', 'Water level', 'unknown']:
            self.assertTrue(sensor_maintenance_required({'sensortype': kind}))
            with self.assertRaises(ValueError): maintenance_values(kind, '', None)
        self.assertEqual(maintenance_values('pH Level', 'Monthly', '2026-01-01')['last_maintenance_date'], '2026-01-01')

    def test_calibration_remains_separate(self):
        from sensor_capabilities import with_sensor_capabilities
        data = with_sensor_capabilities({'sensortype': 'humidity', 'calibration_required': True})
        self.assertFalse(data['maintenance_required'])
        self.assertTrue(data['calibration_required'])
