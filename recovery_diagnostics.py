"""Recovery failure diagnostics without emails, credentials or reset tokens."""
import json
import logging
import os
import re
import uuid
from urllib.parse import urlsplit


def argument_diagnostic(error):
    """Extract only known parameter names and fixed reasons from provider text."""
    message = str(getattr(error, 'message', None) or error).lower()
    match = re.search(r"invalid\s+[`'\"]?(email|url|password|userid|secret)[`'\"]?\s+param", message)
    parameter = match.group(1) if match else 'unknown'
    if 'url host must' in message or 'hostname must' in message:
        return parameter, 'redirect_host_not_allowed', 'Register the redirect hostname as a Web platform in the exact Appwrite project used by this API.'
    if parameter == 'url':
        return parameter, 'redirect_url_invalid', 'Check PASSWORD_RESET_URL for quotes, whitespace, malformed syntax or unsupported URL format.'
    if parameter == 'email':
        return parameter, 'email_argument_invalid', 'Appwrite rejected the email format; check its email validator and the submitted address.'
    return parameter, 'argument_invalid', 'Check the Appwrite request validation logs at this timestamp; the rejected parameter is not identified.'


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
    redirect = os.getenv('PASSWORD_RESET_URL', 'https://apps.farmestates.farm/#/reset-password')
    try:
        redirect_host = urlsplit(redirect).hostname
    except ValueError:
        redirect_host = None
    details = {}
    if kind == 'general_argument_invalid':
        parameter, validation_reason, hint = argument_diagnostic(error)
        details = {'invalid_parameter': parameter, 'validation_reason': validation_reason}
    else:
        hint = hints.get(kind, 'Inspect Appwrite service/mail logs and API connectivity at this timestamp.')
    logging.getLogger('uvicorn.error').warning('password_recovery_failed %s', json.dumps({
        'reference': reference, 'stage': stage, 'reason': reason,
        'upstream_status': status, 'redirect_host': redirect_host,
        'redirect_has_whitespace': any(char.isspace() for char in redirect),
        'redirect_has_wrapping_quotes': redirect.startswith(('"', "'")) or redirect.endswith(('"', "'")),
        **details, 'hint': hint,
    }))
    return reference
