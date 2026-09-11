"""Use a fragment-free URL for Appwrite's recovery redirect validator."""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def password_reset_url():
    value = os.getenv('PASSWORD_RESET_URL', 'https://apps.farmestates.farm/?recovery=1').strip()
    parts = urlsplit(value)
    if parts.fragment == '/reset-password':
        # Preserve the deployed Flutter base path; no server rewrite is needed.
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query['recovery'] = '1'
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))
    return value
