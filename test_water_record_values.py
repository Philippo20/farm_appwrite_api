import unittest
from water_record_values import water_record_values
class WaterTests(unittest.TestCase):
    def test_water_temperature(self):
        self.assertEqual(water_record_values('watering', '', '', '', '24.5'), {'water_temperature':24.5})
        self.assertEqual(water_record_values('watering', '', '', '', '0'), {'water_temperature':0})
        self.assertEqual(water_record_values('daily_monitoring', '100', '50', '10', '24'), {'water_temperature':24})
        for bad in ['nan', 'inf', 'bad']:
            with self.assertRaises(ValueError): water_record_values('watering', '', '', '', bad)
    def test_sources(self):
        self.assertEqual(water_record_values('watering', '120.5', '60', '8'), {'water_bought_litres':120.5, 'water_bought_amount':60, 'ac_water_litres':8})
        self.assertEqual(water_record_values('watering', '', '', '8'), {'ac_water_litres':8})
        self.assertEqual(water_record_values('feeding', '120', '60', '8'), {})
    def test_invalid(self):
        for values in [('1','',''), ('','2',''), ('nan','2',''), ('1','-2',''), ('','','inf'), ('','','abc')]:
            with self.assertRaises(ValueError): water_record_values('watering', *values)
if __name__ == '__main__': unittest.main()
