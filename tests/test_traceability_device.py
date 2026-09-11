import unittest
from traceability_device import device_details

class VisitorDeviceTest(unittest.TestCase):
    def test_visitor_overrides_proxy_agent_and_hints(self):
        data = device_details('node', '?0', 'Linux', {'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile Safari/604.1'})
        self.assertEqual((data['device_type'], data['operating_system'], data['browser']), ('mobile', 'iOS', 'Safari'))

    def test_direct_browser_fallback(self):
        tablet = device_details('Mozilla/5.0 (Linux; Android 14) Chrome/130.0 Safari/537.36')
        self.assertEqual(tablet['device_type'], 'tablet')
        self.assertEqual(tablet['operating_system'], 'Android')
        desktop = device_details('Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Edg/130.0')
        self.assertEqual(desktop['browser'], 'Microsoft Edge')
        self.assertEqual(desktop['device_type'], 'desktop')

    def test_unknown_server_not_desktop(self):
        self.assertEqual(device_details('node')['device_type'], 'unknown')
        self.assertEqual(device_details('')['device_type'], 'unknown')

    def test_bounded_metadata_without_location_override(self):
        data = device_details('node', metadata={'device_type': 'tablet', 'operating_system': 'iPadOS', 'browser': 'a' * 200, 'user_agent': 'b' * 2000, 'country': 'Override'})
        self.assertEqual(data['operating_system'], 'iPadOS')
        self.assertEqual(len(data['browser']), 120)
        self.assertEqual(len(data['user_agent']), 1000)
        self.assertNotIn('country', data)
        self.assertEqual(device_details('node', metadata={'device_type': 'invalid'})['device_type'], 'unknown')
