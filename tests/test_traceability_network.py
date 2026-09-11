import unittest
from traceability_network import visitor_ip, visitor_location

class VisitorNetworkTest(unittest.TestCase):
    def test_visitor_wins_over_hosting_ip(self):
        headers = {'x-visitor-ip': '8.8.8.8', 'do-connecting-ip': '1.1.1.1'}
        self.assertEqual(visitor_ip(headers, True, 'do-connecting-ip', '127.0.0.1'), ('8.8.8.8', 'trusted-proxy'))

    def test_missing_or_invalid_visitor_never_falls_back_to_proxy(self):
        for value in ('', 'invalid'):
            self.assertEqual(visitor_ip({'x-visitor-ip': value, 'do-connecting-ip': '1.1.1.1'}, True, 'do-connecting-ip', '127.0.0.1'), ('unknown', 'unavailable'))

    def test_untrusted_visitor_headers_ignored(self):
        headers = {'x-visitor-ip': '8.8.8.8', 'do-connecting-ip': '1.1.1.1', 'x-visitor-city': 'Fake'}
        self.assertEqual(visitor_ip(headers, False, 'do-connecting-ip', ''), ('1.1.1.1', 'do-connecting-ip'))
        self.assertEqual(visitor_location(headers, False)['city'], '')

    def test_proxy_location_not_mixed_with_host_location(self):
        headers = {'x-visitor-country': 'Ghana', 'x-visitor-city': 'Accra', 'cf-ipcountry': 'US', 'cf-ipcity': 'Hosting city'}
        location = visitor_location(headers, True)
        self.assertEqual(location['country'], 'Ghana')
        self.assertEqual(location['city'], 'Accra')
        self.assertEqual(visitor_location({'cf-ipcity': 'Hosting city'}, True)['city'], '')

    def test_ipv6_supported(self):
        self.assertEqual(visitor_ip({'x-visitor-ip': '[2001:4860:4860::8888]'}, True, '', '')[0], '2001:4860:4860::8888')
