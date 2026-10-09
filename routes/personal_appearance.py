"""Account-owned appearance preferences, shared by every role and device."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from db import db
from main import db_id, db_collection_id1
from routes.messaging import current_member

router = APIRouter(prefix='/me/appearance', tags=['Personal appearance'])
ATTRIBUTE = 'typography_preferences'


class TypographyPreferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    headings: float = Field(default=1.0, ge=0.85, le=1.35, strict=True, allow_inf_nan=False)
    titles: float = Field(default=1.0, ge=0.85, le=1.35, strict=True, allow_inf_nan=False)
    body: float = Field(default=1.0, ge=0.85, le=1.35, strict=True, allow_inf_nan=False)
    labels: float = Field(default=1.0, ge=0.85, le=1.35, strict=True, allow_inf_nan=False)


def read_preferences(profile):
    raw = profile.get(ATTRIBUTE)
    if not raw:
        return TypographyPreferences()
    try:
        return TypographyPreferences.model_validate(json.loads(raw))
    except (TypeError, ValueError):
        logging.getLogger(__name__).warning('Invalid personal typography preferences; using defaults')
        return TypographyPreferences()


@router.get('')
def get_appearance(actor=Depends(current_member)):
    return {'typography': read_preferences(actor).model_dump()}


@router.put('')
def save_appearance(payload: TypographyPreferences, actor=Depends(current_member)):
    try:
        db.update_document(database_id=db_id, collection_id=db_collection_id1,
            document_id=actor['$id'], data={ATTRIBUTE: payload.model_dump_json()})
    except Exception:
        logging.getLogger(__name__).exception('Unable to save personal typography preferences')
        raise HTTPException(503, 'Could not save your text sizes. Please try again.') from None
    return {'typography': payload.model_dump()}
