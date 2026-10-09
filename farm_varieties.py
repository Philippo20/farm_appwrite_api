"""Farm variety assignments and validation of new batches against those IDs."""
import json
from fastapi import HTTPException
from crop_relationships import crop_plant_link, plant_key, variety_matches_plant


def farm_variety_ids(farm):
    values = farm.get('crop_variety_ids') or []
    return list(dict.fromkeys(v for v in values if isinstance(v, str) and v.strip())) if isinstance(values, list) else []


def farm_variety_assignment(raw, plant_id, plant_name, primary, previous, load_plant, load_crop, all_plants):
    previous = previous or {}
    if raw is None:
        # Old clients may update status/team, but cannot silently replace a
        # multi-variety assignment with their single legacy field.
        if farm_variety_ids(previous) and (plant_key(plant_name) != plant_key(previous.get('plant_type')) or
                plant_key(primary) != plant_key(previous.get('plant_variety'))):
            raise HTTPException(422, 'Use the crop variety selection to change this farm\'s varieties.')
        return {}
    try:
        ids = json.loads(raw)
    except (TypeError, ValueError):
        raise HTTPException(422, 'Select valid crop varieties.') from None
    if not isinstance(ids, list) or not 1 <= len(ids) <= 50 or any(
            not isinstance(v, str) or not v.strip() or len(v.strip()) > 36 for v in ids):
        raise HTTPException(422, 'Select between one and 50 crop varieties.')
    ids = list(dict.fromkeys(v.strip() for v in ids))
    saved_parent = previous.get('plant_type_ID') if plant_key(plant_name) == plant_key(previous.get('plant_type')) else ''
    link = crop_plant_link(plant_id or saved_parent, plant_name, load_plant, all_plants,
                          {'plant_type_ID': previous.get('plant_type_ID')} if saved_parent or plant_id == previous.get('plant_type_ID') else {})
    names = []
    for identity in ids:
        try:
            crop = load_crop(identity)
        except Exception:
            raise HTTPException(422, 'A selected crop variety no longer exists. Select a valid variety.') from None
        if not variety_matches_plant(crop, link['plant_type_ID'], link['crop_name']):
            raise HTTPException(422, 'Every selected crop variety must belong to the farm\'s plant type.')
        if str(crop.get('status', 'active')).lower() in {'suspended', 'inactive'} and identity not in farm_variety_ids(previous):
            raise HTTPException(422, 'Select active crop varieties.')
        name = str(crop.get('variety_name') or '').strip()
        if not name:
            raise HTTPException(422, 'A selected crop variety has no name.')
        names.append(name)
    return {'plant_type_ID': link['plant_type_ID'], 'plant_type': link['crop_name'],
            'crop_variety_ids': ids, 'plant_varieties': names, 'plant_variety': names[0]}


def assigned_batch_variety(farm, plant_id, plant_name, variety_name, variety_id, load_crop):
    ids = farm_variety_ids(farm)
    if not ids:
        return {}  # Existing single-variety farms retain legacy API behavior.
    if farm.get('plant_type_ID') and farm['plant_type_ID'] != plant_id:
        raise HTTPException(422, 'Choose the plant type assigned to this farm.')
    if variety_id and variety_id not in ids:
        raise HTTPException(422, 'Choose a crop variety assigned to this farm.')
    candidates = []
    for identity in ([variety_id] if variety_id else ids):
        try:
            crop = load_crop(identity)
        except Exception:
            continue
        if not variety_matches_plant(crop, plant_id, plant_name):
            continue
        if variety_id or plant_key(crop.get('variety_name')) == plant_key(variety_name):
            candidates.append((identity, crop))
    if len(candidates) != 1:
        raise HTTPException(422, 'Choose a valid crop variety assigned to this farm. Edit the farm if its catalog links have changed.')
    identity, crop = candidates[0]
    return {'crop_variety_id': identity, 'plant_variety': crop['variety_name']}
