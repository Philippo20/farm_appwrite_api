"""Stable crop-to-plant links; exact matching only for legacy records."""
from fastapi import HTTPException


def plant_key(value):
    return ' '.join(str(value or '').strip().casefold().split())


def exact_legacy_plant(crop, plants):
    matches = [p for p in plants if not p.get('is_category') and
               plant_key(p.get('name')) == plant_key(crop.get('crop_name')) and plant_key(p.get('name'))]
    return matches[0] if len(matches) == 1 else None


def crop_plant_link(identity, crop_name, load_plant, all_plants, previous=None):
    previous = previous or {}
    identity = (identity or previous.get('plant_type_ID') or '').strip()
    if identity:
        try:
            plant = load_plant(identity)
        except Exception:
            raise HTTPException(422, 'The selected plant type is unavailable. Select a valid plant type.') from None
    else:
        plant = exact_legacy_plant({'crop_name': crop_name}, all_plants())
        if plant is None:
            raise HTTPException(422, 'Select a plant type to link this crop variety. The crop name alone is not a unique link.')
        identity = plant['$id']
    if plant.get('is_category') or (str(plant.get('status', 'active')).lower() != 'active' and identity != previous.get('plant_type_ID')):
        raise HTTPException(422, 'Select an active plant type, not a plant category.')
    return {'plant_type_ID': identity, 'crop_name': plant['name']}


def variety_matches_plant(crop, identity, name):
    linked = str(crop.get('plant_type_ID') or '').strip()
    return linked == identity if linked else plant_key(crop.get('crop_name')) == plant_key(name)
