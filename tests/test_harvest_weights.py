import unittest
from harvest_weights import crop_for_batch, harvest_weight_kg


class HarvestWeightTests(unittest.TestCase):
    def test_grams_convert_to_kg_without_whole_kg_rounding(self):
        self.assertEqual(harvest_weight_kg(100, {'harvesting_weight': 113}), 11.3)
        self.assertEqual(harvest_weight_kg(1, {'harvesting_weight': 20}), .02)
        self.assertEqual(harvest_weight_kg(0, {'harvesting_weight': 113}), 0)

    def test_missing_invalid_and_unknown_stay_unknown(self):
        for weight in [None, '', 0, -1, 'NaN', 'Infinity']:
            self.assertIsNone(harvest_weight_kg(10, {'harvesting_weight': weight}))
        self.assertIsNone(harvest_weight_kg(None, {'harvesting_weight': 113}))

    def test_id_wins_and_legacy_matches_must_be_unique_and_same_plant(self):
        crops = [{'$id': 'a', 'plant_type_ID': 'p', 'variety_name': 'Green'},
                 {'$id': 'b', 'plant_type_ID': 'q', 'variety_name': 'Green'}]
        self.assertEqual(crop_for_batch({'crop_variety_id': 'b'}, crops), crops[1])
        self.assertEqual(crop_for_batch({'plant_type_ID': 'p', 'plant_variety': 'green'}, crops), crops[0])
        self.assertIsNone(crop_for_batch({'crop_variety_id': 'missing'}, crops))
