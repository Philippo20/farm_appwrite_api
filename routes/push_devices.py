from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from routes.messaging import current_member
import push_notifications as push

router = APIRouter(prefix='/push', tags=['Push notifications'])

class Device(BaseModel):
    token: str = Field(min_length=20, max_length=4096, pattern=r'^\S+$')

@router.post('/devices')
def register_device(payload: Device, actor=Depends(current_member)):
    if not push.enabled():
        raise HTTPException(503, 'Push delivery is not configured on this server yet.')
    push.register(payload.token, actor)
    return {'registered': True}

@router.delete('/devices')
def unregister_device(payload: Device, actor=Depends(current_member)):
    push.unregister(payload.token, actor)
    return {'removed': True}
