"""Super Admin-only email settings; secrets never enter global config responses."""
import json
import smtplib
from fastapi import APIRouter, Depends, HTTPException, Body
from appwrite.exception import AppwriteException
from pydantic import BaseModel, EmailStr, ValidationError
from routes.messaging import current_member
from db import db
from main import db_id, db_collection_id18
from audit_utils import write_audit
from email_delivery import EmailSettings, store_settings, public_settings, send_email

email_settings_router = APIRouter(prefix='/system-config/email', tags=['Email Settings'])


def super_admin(actor=Depends(current_member)):
    if str(actor.get('role', '')).lower().replace(' ', '').replace('_', '') != 'superadmin':
        raise HTTPException(403, 'Only Super Admin can manage email settings')
    return actor


def load_settings():
    try:
        document = db.get_document(database_id=db_id, collection_id=db_collection_id18, document_id='email')
        return json.loads(document.get('email_settings_json') or '{}')
    except AppwriteException as error:
        if error.code != 404:
            raise
        return store_settings(EmailSettings(), {})


@email_settings_router.get('')
def get_settings(actor=Depends(super_admin)):
    return {'config': public_settings(load_settings())}


@email_settings_router.put('')
def update_settings(payload: dict = Body(...), actor=Depends(super_admin)):
    try:
        payload = EmailSettings.model_validate(payload)
    except ValidationError as error:
        # Do not echo submitted SMTP credentials in validation responses.
        raise HTTPException(422, '; '.join(item['msg'] for item in error.errors(include_input=False))) from error
    previous = load_settings()
    try:
        settings = store_settings(payload, previous)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    data = {'email_settings_json': json.dumps(settings)}
    try:
        db.update_document(database_id=db_id, collection_id=db_collection_id18, document_id='email', data=data)
    except AppwriteException as error:
        if error.code != 404:
            raise HTTPException(503, 'Unable to save email settings. Check the email settings database migration.') from error
        db.create_document(database_id=db_id, collection_id=db_collection_id18, document_id='email', data=data, permissions=[])
    write_audit(action_type='Update', collection_name='Email Settings', performed_by_id=actor['$id'], performed_by_role='superadmin', action_details='Updated email delivery settings', previous_data=public_settings(previous), new_data=public_settings(settings))
    return {'config': public_settings(settings)}


class TestEmail(BaseModel):
    recipient: EmailStr


@email_settings_router.post('/test')
def test_email(payload: TestEmail, actor=Depends(super_admin)):
    try:
        send_email(load_settings(), str(payload.recipient), 'Farm Estates email configuration test', 'Your saved SMTP configuration successfully sent this test email.')
    except smtplib.SMTPAuthenticationError as error:
        raise HTTPException(400, 'SMTP authentication failed. Check the username and password.') from error
    except Exception as error:
        raise HTTPException(400, 'Email delivery failed. Check the saved SMTP settings, encryption key, and server connection.') from error
    return {'message': 'Test email accepted by the SMTP server'}
