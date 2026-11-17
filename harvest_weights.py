"""Catalog harvest weights are grams per harvested head; batch totals are kg."""
from decimal import Decimal, InvalidOperation


def crop_for_batch(batch, crops):
    identity = batch.get('crop_variety_id')
    if identity:
        return next((c for c in crops if c.get('$id') == identity), None)
    matches = [c for c in crops if c.get('plant_type_ID') == batch.get('plant_type_ID')
               and str(c.get('variety_name', '')).strip().casefold() == str(batch.get('plant_variety', '')).strip().casefold()]
    return matches[0] if len(matches) == 1 else None


def harvest_weight_kg(count, crop):
    if count is None or count < 0 or not crop:
        return None
    try:
        grams = Decimal(str(crop.get('harvesting_weight')))
        if not grams.is_finite() or grams <= 0:
            return None
        return float((Decimal(count) * grams / 1000).quantize(Decimal('0.000001')))
    except (InvalidOperation, ValueError, TypeError):
        return None
