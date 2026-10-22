"""Exclusive links between registered equipment and controller-reported outputs."""
import os
from fastapi import HTTPException
from appwrite.exception import AppwriteException
from appwrite.query import Query
from controller_activity import EQUIPMENT_OUTPUTS, activity_key

BINDINGS = os.getenv('APPWRITE_CONTROLLER_BINDINGS_COLLECTION', 'controller_output_bindings')

def validate_link(db, database, devices, kind, farm, controller_id, output):
    if kind not in EQUIPMENT_OUTPUTS:
        if controller_id or output:
            raise HTTPException(422, 'Only lights and pumps can link to controller outputs.')
        return
    if output not in EQUIPMENT_OUTPUTS[kind] or not controller_id:
        raise HTTPException(422, 'Select a controller and a supported equipment output.')
    try:
        parent = db.get_document(database, devices, controller_id)
    except AppwriteException as error:
        if error.code != 404: raise
        raise HTTPException(422, 'The selected controller no longer exists.') from None
    if parent.get('sensortype') != 'command_device' or parent.get('farmID') != farm:
        raise HTTPException(422, 'Choose a Command Device registered on this farm.')

def reserve(db, database, controller, output, device_id):
    identity = activity_key(controller, output)
    try:
        db.create_document(database, BINDINGS, identity,
            {'controller_id': controller, 'output': output, 'device_id': device_id}, permissions=[])
        return True
    except AppwriteException as error:
        if error.code != 409: raise
        saved = db.get_document(database, BINDINGS, identity)
        if saved['device_id'] != device_id:
            raise HTTPException(409, 'This controller output already belongs to another registered device.') from None
        return False

def release(db, database, device):
    if not device.get('controller_id'): return
    identity = activity_key(device['controller_id'], device['controller_output'])
    try:
        saved = db.get_document(database, BINDINGS, identity)
        if saved['device_id'] == device['$id']:
            db.delete_document(database, BINDINGS, identity)
    except AppwriteException as error:
        if error.code != 404: raise

def guard_controller_change(db, database, devices, previous, kind=None, farm=None):
    if previous.get('sensortype') != 'command_device': return
    if kind == 'command_device' and farm == previous.get('farmID'): return
    children = db.list_documents(database, devices,
        queries=[Query.equal('controller_id', [previous['$id']]), Query.limit(1)])['documents']
    if children:
        raise HTTPException(409, 'Remove or reassign the linked equipment before changing or deleting this controller.')
