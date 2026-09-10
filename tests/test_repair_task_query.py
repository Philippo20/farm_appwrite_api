import ast
from pathlib import Path
from typing import Optional
import unittest
from unittest.mock import Mock
from appwrite.query import Query

class RepairTaskQueryTest(unittest.TestCase):
    def test_assignee_and_pagination_are_sent_to_database(self):
        tree = ast.parse(Path('routes/r23_farm_tasks.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_farm_tasks')
        fn.decorator_list = []
        db = Mock()
        db.list_documents.return_value = {'documents': [{'title': 'Repair pump'}]}
        ns = {'Optional': Optional, 'ApiQuery': lambda default, **kwargs: default, 'Query': Query, 'db': db, 'db_id': 'db', 'db_collection_id23': 'tasks', 'HTTPException': Exception}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'tasks', 'exec'), ns)
        result = ns['get_farm_tasks']('tech-1', 100, 100)
        filters = db.list_documents.call_args.kwargs['queries']
        self.assertIn(Query.equal('assigned_to_id', ['tech-1']), filters)
        self.assertIn(Query.offset(100), filters)
        self.assertIn(Query.limit(100), filters)
        self.assertEqual(result['users'][0]['title'], 'Repair pump')
