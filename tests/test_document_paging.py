import json
import unittest
from unittest.mock import Mock
from document_paging import list_all_documents

class PagingTests(unittest.TestCase):
    def test_reads_beyond_first_page(self):
        db = Mock()
        db.list_documents.side_effect = [
            {"documents": [{"$id": str(i)} for i in range(100)]},
            {"documents": [{"$id": "100"}, {"$id": "101"}]},
        ]
        result = list_all_documents(db, database_id="db", collection_id="sales")
        self.assertEqual(result["total"], 102)
        queries = db.list_documents.call_args.kwargs["queries"]
        self.assertTrue(any(json.loads(q).get("method") == "offset" and
                            json.loads(q).get("values") == [100] for q in queries))

    def test_errors_are_not_silently_reported_as_partial_totals(self):
        db = Mock()
        db.list_documents.side_effect = RuntimeError("unavailable")
        with self.assertRaises(RuntimeError):
            list_all_documents(db, database_id="db", collection_id="sales")
