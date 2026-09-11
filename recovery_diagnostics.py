"""Recovery failure diagnostics without emails, credentials or reset tokens."""
import json
import logging
import os
import uuid
from urllib.parse import urlsplit


def log_recovery_failure(error, stage):
    reference = uuid.uuid4().hex[:12]
    kind = getattr(error, 'type', '')
    # Only recognized provider codes are logged; never log raw provider messages.
    hints = {
        'general_smtp_disabled': 'Configure SMTP on Appwrite for authentication emails.',
        'general_smtp_error': 'Check Appwrite SMTP credentials, TLS, sender and mail service logs.',
        'general_argument_invalid': 'Check PASSWORD_RESET_URL and its host in Appwrite project platforms.',
        'general_uri_invalid': 'Check PASSWORD_RESET_URL and its host in Appwrite project platforms.',
        'general_rate_limit_exceeded': 'Wait for the Appwrite recovery rate limit to reset.',
        'project_not_found': 'Check APPWRITE_ENDPOINT and APPWRITE_PROJECT_ID.',
        'project_unknown': 'Check APPWRITE_ENDPOINT and APPWRITE_PROJECT_ID.',
        'user_password_reset_required': 'Inspect Appwrite authentication policy.',
        'user_invalid_token': 'Request a new reset link.',
    }
    reason = kind if kind in hints else 'upstream_failure'
    status = getattr(error, 'code', None)
    if not isinstance(status, int):
        status = None
    try:
        redirect_host = urlsplit(os.getenv('PASSWORD_RESET_URL', 'https://apps.farmestates.farm/#/reset-password')).hostname
    except ValueError:
        redirect_host = None
    logging.getLogger('uvicorn.error').warning('password_recovery_failed %s', json.dumps({
        'reference': reference, 'stage': stage, 'reason': reason,
        'upstream_status': status, 'redirect_host': redirect_host,
        'hint': hints.get(kind, 'Inspect Appwrite service/mail logs and API connectivity at this timestamp.'),
    }))
    return reference
