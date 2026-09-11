import unittest
from unittest.mock import patch
from recovery_diagnostics import argument_diagnostic, log_recovery_failure


class DiagnosticsTests(unittest.TestCase):
    def test_host_rejection_is_distinguished_from_bad_url(self):
        result = argument_diagnostic(Exception('Invalid `url` param: URL host must be one of: localhost'))
        self.assertEqual(result[:2], ('url', 'redirect_host_not_allowed'))
        result = argument_diagnostic(Exception('Invalid `url` param: Value must be a valid URL'))
        self.assertEqual(result[:2], ('url', 'redirect_url_invalid'))

    def test_email_rejection_is_identified(self):
        self.assertEqual(argument_diagnostic(Exception('Invalid `email` param: Invalid email'))[:2],
                         ('email', 'email_argument_invalid'))

    def test_sdk_message_attribute_is_supported_without_logging_values(self):
        error = Exception('fallback')
        error.message = 'Invalid `email` param: private@example.com secret-token'
        error.type = 'general_argument_invalid'
        error.code = 400
        with self.assertLogs('uvicorn.error') as logs:
            log_recovery_failure(error, 'request')
        self.assertIn('email_argument_invalid', logs.output[0])
        self.assertNotIn('private@example.com', logs.output[0])
        self.assertNotIn('secret-token', logs.output[0])

    def test_url_configuration_flags_do_not_log_full_url(self):
        error = Exception('Invalid `url` param: invalid URL')
        error.type = 'general_argument_invalid'
        with patch.dict('os.environ', {'PASSWORD_RESET_URL': '"https://example.com/?secret=hidden "'}):
            with self.assertLogs('uvicorn.error') as logs:
                log_recovery_failure(error, 'request')
        self.assertIn('"redirect_has_whitespace": true', logs.output[0])
        self.assertIn('"redirect_has_wrapping_quotes": true', logs.output[0])
        self.assertNotIn('hidden', logs.output[0])
