"""Encrypted SMTP configuration and reusable platform email delivery."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field, EmailStr, model_validator
from typing import Literal


class EmailSettings(BaseModel):
    enabled: bool = False
    host: str = Field(default='', max_length=253)
    port: int = Field(default=587, ge=1, le=65535)
    security: Literal['starttls', 'ssl'] = 'starttls'
    username: str = Field(default='', max_length=320)
    password: str = Field(default='', max_length=1000)
    clear_password: bool = False
    sender_name: str = Field(default='Farm Estates', max_length=120)
    sender_email: str = Field(default='', max_length=320)
    reply_to: str = Field(default='', max_length=320)
    farm_alerts: bool = True
    workflow_alerts: bool = True
    account_alerts: bool = True

    @model_validator(mode='after')
    def validate_fields(self):
        from pydantic import TypeAdapter
        for name in ('host', 'username', 'sender_name', 'sender_email', 'reply_to'):
            value = getattr(self, name).strip()
            if '\r' in value or '\n' in value:
                raise ValueError('Email settings cannot contain line breaks')
            setattr(self, name, value)
        if self.host and any(c in self.host for c in '/:@ '):
            raise ValueError('SMTP host must be a hostname, without a URL scheme or port')
        for name in ('sender_email', 'reply_to'):
            value = getattr(self, name)
            if value:
                TypeAdapter(EmailStr).validate_python(value)
        if self.enabled and (not self.host or not self.sender_email):
            raise ValueError('SMTP host and sender email are required when email is enabled')
        return self


def cipher():
    key = os.getenv('EMAIL_SETTINGS_ENCRYPTION_KEY', '').strip()
    if not key:
        raise ValueError('Configure EMAIL_SETTINGS_ENCRYPTION_KEY on the API before storing SMTP credentials')
    return Fernet(key.encode())


def store_settings(payload, previous):
    settings = payload.model_dump(exclude={'password', 'clear_password'})
    encrypted = previous.get('password_encrypted', '')
    if payload.clear_password:
        encrypted = ''
    elif payload.password:
        encrypted = cipher().encrypt(payload.password.encode()).decode()
    settings['password_encrypted'] = encrypted
    if settings['enabled'] and settings['username'] and not encrypted:
        raise ValueError('SMTP password is required for authenticated delivery')
    return settings


def public_settings(settings):
    return {**{key: value for key, value in settings.items() if key != 'password_encrypted'},
            'password_configured': bool(settings.get('password_encrypted'))}


def send_email(settings, recipient, subject, body, category=None):
    if category is not None:
        if category not in {'farm_alerts', 'workflow_alerts', 'account_alerts'}:
            raise ValueError('Unsupported email category')
        if not settings.get('enabled') or not settings.get(category, True):
            return False
    if not settings.get('host') or not settings.get('sender_email'):
        raise ValueError('Save SMTP host and sender email before sending a test')
    message = EmailMessage()
    message['From'] = formataddr((settings.get('sender_name', ''), settings['sender_email']))
    message['To'] = recipient
    message['Subject'] = subject
    if settings.get('reply_to'):
        message['Reply-To'] = settings['reply_to']
    message.set_content(body)
    context = ssl.create_default_context()
    factory = smtplib.SMTP_SSL if settings.get('security') == 'ssl' else smtplib.SMTP
    kwargs = {'timeout': 15}
    if factory is smtplib.SMTP_SSL:
        kwargs['context'] = context
    with factory(settings['host'], settings['port'], **kwargs) as smtp:
        if settings.get('security') != 'ssl':
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        if settings.get('username'):
            encrypted = settings.get('password_encrypted', '')
            if not encrypted:
                raise ValueError('SMTP password is not configured')
            smtp.login(settings['username'], cipher().decrypt(encrypted.encode()).decode())
        smtp.send_message(message)
    return True
