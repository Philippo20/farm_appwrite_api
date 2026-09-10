import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import unittest
from unittest.mock import Mock
from appwrite.query import Query

class RequestError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code

class SensorDateQueryTest(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path('routes/r11_sensors.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_sensor_readings_by_serial')
        fn.decorator_list = []
        self.db = Mock()
        self.db.list_documents.return_value = {'total': 0, 'documents': []}
        ns = {'Optional': Optional, 'datetime': datetime, 'timezone': timezone, 'ApiQuery': lambda default, **kwargs: default, 'Query': Query, 'HTTPException': RequestError, 'db': self.db, 'db_id': 'db', 'db_collection_id21': 'readings'}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'sensor_query', 'exec'), ns)
        self.query = ns['get_sensor_readings_by_serial']

    def test_date_bounds_and_page(self):
        start, end = datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 1, 3, tzinfo=timezone.utc)
        self.query('TEMP-1', start, end, 500)
        filters = self.db.list_documents.call_args.kwargs['queries']
        self.assertIn(Query.equal('serial_number', ['TEMP-1']), filters)
        self.assertIn(Query.greater_than_equal('timestamp', start.isoformat()), filters)
        self.assertIn(Query.less_than('timestamp', end.isoformat()), filters)
        self.assertIn(Query.offset(500), filters)

    def test_reversed_range_is_rejected(self):
        with self.assertRaises(RequestError) as error:
            self.query('TEMP-1', datetime(2025, 1, 3), datetime(2025, 1, 1))
        self.assertEqual(error.exception.status_code, 400)
        self.db.list_documents.assert_not_called()
