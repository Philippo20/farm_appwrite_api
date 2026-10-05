"""Temporary credentials and short-lived, purpose-bound onboarding challenges."""
import json
import secrets
import string
from cryptography.fernet import InvalidToken
from email_delivery import cipher


def generate_temporary_password():
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(8))
        if (any(c.islower() for c in password) and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password) and any(c in '!@#$%' for c in password)):
            return password


def make_challenge(user_id, profile_id, session_secret):
    return cipher().encrypt(json.dumps({'purpose':'first_password', 'user_id':user_id,
        'profile_id':profile_id, 'session_secret':session_secret}).encode()).decode()


def read_challenge(token):
    try:
        data = json.loads(cipher().decrypt(token.encode(), ttl=900))
        if data.get('purpose') != 'first_password' or not all(data.get(k) for k in ('user_id','profile_id','session_secret')):
            raise ValueError()
        return data
    except (InvalidToken, ValueError, TypeError, KeyError):
        raise ValueError('This password-change session expired. Sign in again.')
