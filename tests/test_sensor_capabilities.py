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
