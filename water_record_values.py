import math

def water_record_values(record_type, bought_litres, bought_amount, ac_litres, water_temperature=""):
    raw = {'water_bought_litres': bought_litres, 'water_bought_amount': bought_amount, 'ac_water_litres': ac_litres}
    if record_type not in {'watering', 'daily_monitoring'}:
        return {}
    if record_type != 'watering':
        raw = {}
    values = {}
    for key, value in raw.items():
        if value is None or str(value).strip() == '':
            continue
        try:
            number = float(value)
        except (ValueError, TypeError):
            raise ValueError('Water quantities and purchase amount must be valid numbers.')
        if not math.isfinite(number) or number < 0:
            raise ValueError('Water quantities and purchase amount must be zero or positive finite numbers.')
        values[key] = number
    if ('water_bought_litres' in values) != ('water_bought_amount' in values):
        raise ValueError('Enter both litres bought and the purchase amount, or leave both blank.')
    if water_temperature is not None and str(water_temperature).strip():
        try:
            temperature = float(water_temperature)
        except (ValueError, TypeError):
            raise ValueError('Water temperature must be a valid number.')
        if not math.isfinite(temperature):
            raise ValueError('Water temperature must be a finite number.')
        values['water_temperature'] = temperature
    return values
