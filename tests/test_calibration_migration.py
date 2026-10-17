import unittest
from unittest.mock import Mock
from appwrite.exception import AppwriteException
from migrate_calibration_events import migrate

class CalibrationMigrationTests(unittest.TestCase):
    def setUp(self):
        self.fields = {}; self.indexes = {}; self.db = Mock()
        self.db.get_collection.return_value = {'$permissions': []}
        def store(name, kind, required, size=None):
            if name in self.fields: raise AppwriteException('duplicate', 409)
            self.fields[name] = {'key': name, 'type': kind, 'required': required,
                                 'size': size, 'status': 'available'}
        self.db.create_string_attribute.side_effect = lambda d,c,k,s,r: store(k,'string',r,s)
        self.db.create_integer_attribute.side_effect = lambda d,c,k,r,**kw: store(k,'integer',r)
        self.db.create_datetime_attribute.side_effect = lambda d,c,k,r: store(k,'datetime',r)
        self.db.create_boolean_attribute.side_effect = lambda d,c,k,r: store(k,'boolean',r)
        self.db.get_attribute.side_effect = lambda d,c,k: self.fields[k]
        def index(d,c,k,t,attrs):
            if k in self.indexes: raise AppwriteException('duplicate',409)
            self.indexes[k] = {'key': k, 'type':t, 'attributes':attrs, 'status':'available'}
        self.db.create_index.side_effect = index
        self.db.get_index.side_effect = lambda d,c,k: self.indexes[k]
    def test_migration_is_private_indexed_and_idempotent(self):
        migrate(self.db, 'db'); migrate(self.db, 'db')
        self.assertEqual(len(self.indexes), 3)
        self.assertEqual(self.fields['payload']['size'], 8192)
        self.assertEqual(self.db.create_collection.call_args.kwargs['permissions'], [])
    def test_public_or_incompatible_storage_is_rejected(self):
        self.db.get_collection.return_value = {'$permissions': ['read("any")']}
        with self.assertRaises(RuntimeError): migrate(self.db,'db')
        self.db.get_collection.return_value = {'$permissions': []}
        migrate(self.db,'db'); self.fields['payload']['size'] = 10
        with self.assertRaises(RuntimeError): migrate(self.db,'db')
