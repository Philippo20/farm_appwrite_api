import unittest
from production_planning import growth_stage_at, record_growth_plan
from water_record_values import water_parameter_values
from unittest.mock import Mock

class RecordGrowthTests(unittest.TestCase):
    plan = {'stages': [{'name': 'Sprouting', 'days': 7}, {'name': 'Leaf Development', 'days': 14}, {'name': 'Harvest stage', 'days': 7}]}
    def test_boundaries_and_backdated_records(self):
        for day, name in [(1, 'Sprouting'), (7, 'Sprouting'), (8, 'Leaf Development'), (21, 'Leaf Development'), (22, 'Harvest stage'), (29, 'Harvest stage')]:
            self.assertEqual(growth_stage_at(self.plan, '2026-10-01', f'2026-10-{day:02}T23:59:00'), name)
    def test_before_start_and_missing_plan(self):
        with self.assertRaises(ValueError): growth_stage_at(self.plan, '2026-10-02', '2026-10-01')
        self.assertEqual(growth_stage_at({}, '2026-10-01', '2026-10-02'), '')
    def test_snapshot_wins_over_changed_catalog(self):
        lookup = Mock(return_value={'production_plan': {'stages': [{'name': 'Changed', 'days': 2}]}})
        self.assertEqual(record_growth_plan({'production_plan': self.plan, 'plant_type_ID': 'plant'}, lookup), self.plan)
        lookup.assert_not_called()
        self.assertEqual(record_growth_plan({'plant_type_ID': 'plant'}, lookup)['stages'][0]['name'], 'Changed')
    def test_ph_and_ec_remain_separate(self):
        self.assertEqual(water_parameter_values('6.2', '1.5'), {'ph': 6.2, 'ec': 1.5})
        self.assertEqual(water_parameter_values('', '0'), {'ec': 0.0})
        for ph, ec in [('15', '1'), ('nan', '1'), ('6', 'inf'), ('6', '-1')]:
            with self.assertRaises(ValueError): water_parameter_values(ph, ec)
