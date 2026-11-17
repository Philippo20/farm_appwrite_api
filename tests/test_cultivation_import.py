import unittest
from datetime import date
from unittest.mock import Mock
from appwrite.exception import AppwriteException
from batch_numbers import allocate_number, parse_number
from cultivation_import import prepare, write_once, provenance
from production_planning import reminder_events


class CultivationTests(unittest.TestCase):
    def setUp(self):
        self.values = ['LL 20-03-2026-4', 'Rijk zwaana - Batavia', '2026-03-20'] + [None] * 17
        self.source = {'Batch Register': [{'row': 4, 'values': self.values}],
                       'Daily Growth Log': [], 'Nutrient & EC Log': []}
        self.farm = {'$id': 'farm', 'name': 'Farm', 'plant_type': 'Lettuce', 'crop_variety_ids': ['crop']}
        self.crops = [{'$id': 'crop', 'variety_name': 'Batavia', 'plant_type_ID': 'plant'}]

    def plan(self):
        return prepare(self.source, self.farm, self.crops, {'$id': 'admin'}, date(2026, 11, 17))

    def test_authoritative_columns_and_unknown_quantities(self):
        self.values[2] = '2026-03-21'
        batch = self.plan()['batches'][0]
        self.assertEqual(batch['batch_no'], 'BL 21-03-2026-4')
        self.assertEqual(batch['plant_variety'], 'Batavia')
        self.assertIn('LL 20-03-2026-4', batch['source_data'])
        self.assertIsNone(batch['total_seeds_nursed'])
        self.assertIsNone(batch['total_transplanted'])
        self.assertEqual(batch['production_status'], 'Unknown')

    def test_zero_is_not_missing_and_harvest_date_beats_stale_status(self):
        self.values[7] = 0
        self.values[6] = '2026-05-20'
        self.values[18] = 'Nursery'
        batch = self.plan()['batches'][0]
        self.assertEqual(batch['total_seeds_nursed'], 0)
        self.assertEqual(batch['production_status'], 'Harvested')
        self.assertEqual(batch['actual_harvest_date'], '2026-05-20')

    def test_water_ph_ec_and_multiple_samples_preserved(self):
        values = ['2026-03-22', self.values[0], 1.2, 6.4, 24, 30, 'AC', 5, 'Top up', None, 'Checked']
        self.source['Nutrient & EC Log'] = [{'row': n, 'values': values} for n in (4, 5)]
        records = self.plan()['records']
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]['id'], records[1]['id'])
        self.assertEqual(records[0]['data']['ec'], 1.2)
        self.assertEqual(records[0]['data']['ph'], 6.4)
        self.assertEqual(records[0]['data']['water_volume_litres'], 5)

    def test_missing_sequence_resolves_only_unique_original(self):
        self.source['Daily Growth Log'] = [{'row': 4, 'values': ['2026-03-22', 'LL 20-03-2026', None, 3, 5, 'Good', '']}]
        self.assertEqual(len(self.plan()['records']), 1)
        duplicate = self.values.copy(); duplicate[0] = 'LL 20-03-2026-5'
        self.source['Batch Register'].append({'row': 5, 'values': duplicate})
        self.assertFalse(self.plan()['records'])

    def test_ambiguous_future_and_preseeding_dates_held(self):
        self.source['Daily Growth Log'] = [{'row': n, 'values': [day, batch, None, 3, None, '', '']} for n, day, batch in
            [(4, '2026-12-01', self.values[0]), (5, '2026-03-19', self.values[0]), (6, '2026-03-22', None)]]
        result = self.plan()
        self.assertEqual(len(result['held']), 3)
        self.assertFalse(result['records'])

    def test_placeholders_do_not_create_observations(self):
        self.source['Daily Growth Log'] = [{'row': 4, 'values': ['2026-03-22', self.values[0], None, None, None, None, None]}]
        self.assertEqual(self.plan()['skipped_placeholders'], 1)
        self.assertFalse(self.plan()['records'])

    def test_retry_never_overwrites_or_duplicates(self):
        db = Mock(); data = provenance('Daily Growth Log', 4, [1, 2])
        db.create_document.side_effect = AppwriteException('Duplicate', 409)
        db.get_document.return_value = data
        self.assertEqual(write_once(db, 'db', 'records', 'id', data), 'existing')
        with self.assertRaises(ValueError):
            write_once(db, 'db', 'records', 'id', provenance('Daily Growth Log', 4, [1, 3]))
        db.update_document.assert_not_called()

    def test_sequence_reservation_handles_race(self):
        db = Mock(); db.create_document.side_effect = [AppwriteException('Duplicate', 409), {}]
        result = allocate_number(db, 'db', 'farm', 'BL', date(2026, 11, 17),
            [{'farmID': 'farm', 'batch_no': 'BL 20-03-2026-4'}], [])
        self.assertEqual(result, 'BL 17-11-2026-6')
        self.assertEqual(parse_number('BL 4-1-26-2'), ('BL', date(2026, 1, 4), 2))

    def test_historical_import_does_not_emit_old_reminders(self):
        self.assertEqual(list(reminder_events([{'historical_import': True}], date(2026, 11, 17))), [])

    def test_numbers_are_unique_across_farms(self):
        db = Mock()
        number = allocate_number(db, 'db', 'second-farm', 'BL', date(2026, 11, 17),
            [{'farmID': 'first-farm', 'batch_no': 'BL 17-11-2026-6'}], [])
        self.assertEqual(number, 'BL 17-11-2026-7')


if __name__ == '__main__': unittest.main()
