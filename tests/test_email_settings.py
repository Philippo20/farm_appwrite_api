import os
import unittest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from email_delivery import EmailSettings, store_settings, public_settings, send_email

class EmailSettingsTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'EMAIL_SETTINGS_ENCRYPTION_KEY': Fernet.generate_key().decode()})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_password_encrypted_preserved_and_never_returned(self):
        settings = store_settings(EmailSettings(password='test-password'), {})
        self.assertNotEqual(settings['password_encrypted'], 'test-password')
        self.assertNotIn('password_encrypted', public_settings(settings))
        self.assertTrue(public_settings(settings)['password_configured'])
        self.assertEqual(store_settings(EmailSettings(), settings)['password_encrypted'], settings['password_encrypted'])
        self.assertEqual(store_settings(EmailSettings(clear_password=True), settings)['password_encrypted'], '')

    def test_validation(self):
        for data in [{'port': 0}, {'security': 'none'}, {'enabled': True}, {'sender_name': 'Bad\r\nBcc: other@example.com'}]:
            with self.assertRaises(ValueError): EmailSettings(**data)

    def test_preferences_prevent_delivery(self):
        with patch('email_delivery.smtplib.SMTP') as smtp:
            self.assertFalse(send_email({'enabled': False}, 'test@example.com', 'Test', 'Body', 'workflow_alerts'))
            self.assertFalse(send_email({'enabled': True, 'farm_alerts': False}, 'test@example.com', 'Test', 'Body', 'farm_alerts'))
            smtp.assert_not_called()

    def test_starttls_before_login_and_send(self):
        settings = store_settings(EmailSettings(host='smtp.example.com', sender_email='sender@example.com', username='user', password='secret'), {})
        with patch('email_delivery.smtplib.SMTP') as factory:
            smtp = factory.return_value.__enter__.return_value
            self.assertTrue(send_email(settings, 'recipient@example.com', 'Test', 'Body'))
            smtp.starttls.assert_called_once()
            smtp.login.assert_called_once_with('user', 'secret')
            smtp.send_message.assert_called_once()
            calls = [call[0] for call in smtp.method_calls]
            self.assertLess(calls.index('starttls'), calls.index('login'))

    def test_ssl_transport(self):
        settings = store_settings(EmailSettings(host='smtp.example.com', sender_email='sender@example.com', security='ssl', port=465), {})
        with patch('email_delivery.smtplib.SMTP_SSL') as factory:
            send_email(settings, 'recipient@example.com', 'Test', 'Body')
            factory.return_value.__enter__.return_value.starttls.assert_not_called()
            self.assertIn('context', factory.call_args.kwargs)
