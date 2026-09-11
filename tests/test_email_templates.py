import os
import unittest
from unittest.mock import patch

from email_templates import render_alert


class EmailTemplateTest(unittest.TestCase):
    def test_untrusted_text_is_escaped_and_lines_preserved(self):
        plain, html = render_alert('<script>alert(1)</script>', 'First\n<b>Second</b>',
                                   recipient_name='<img src=x>', recipient_role='farm_manager')
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=x>', html)
        self.assertIn('First<br>&lt;b&gt;Second&lt;/b&gt;', html)
        self.assertIn('Farm Manager', html)
        self.assertIn('First\n<b>Second</b>', plain)

    def test_every_role_and_category_uses_the_template(self):
        for role in ('superadmin', 'admin', 'farm_owner', 'farm_manager', 'caretaker',
                     'technician', 'sales_manager', 'sales_personnel', 'new_custom_role'):
            for category in ('farm_alerts', 'workflow_alerts', 'account_alerts', None):
                with self.subTest(role=role, category=category):
                    plain, html = render_alert('Update', 'Real notification',
                                               recipient_name='Ama', recipient_role=role,
                                               category=category)
                    self.assertIn('Hello Ama,', html)
                    self.assertIn('Real notification', html)
                    self.assertIn('Open Farm Estates:', plain)

    def test_configured_link_and_unsafe_link_fallback(self):
        with patch.dict(os.environ, {'EMAIL_APP_URL': 'https://example.com/?a=1&b=2'}):
            self.assertIn('href="https://example.com/?a=1&amp;b=2"', render_alert('Title', 'Body')[1])
        for url in ('javascript:alert(1)', 'https://user:password@example.com', 'http://example.com'):
            with patch.dict(os.environ, {'EMAIL_APP_URL': url}):
                self.assertIn('href="https://apps.farmestates.farm/"', render_alert('Title', 'Body')[1])

    def test_missing_profile_fields(self):
        plain, html = render_alert('Title', 'Body', recipient_name=None, recipient_role=None)
        self.assertIn('Hello,', plain)
        self.assertNotIn('None', html)
