import unittest
from unittest.mock import Mock
from appwrite.exception import AppwriteException
from migrate_controller_activity import migrate
from controller_activity import EQUIPMENT_OUTPUTS

class ControllerMigrationTests(unittest.TestCase):
    def setUp(self):
        self.fields = {('devices', 'sensortype'): {'key': 'sensortype', 'type': 'string', 'required': True,
            'elements': ['temperature', 'command_device', *EQUIPMENT_OUTPUTS], 'status': 'available'}}
        self.indexes = {}; self.db = Mock()
        self.db.get_collection.return_value = {'$permissions': []}
        def store(collection, name, kind, required, size=None):
            identity = (collection, name)
            if identity in self.fields: raise AppwriteException('duplicate', 409)
            self.fields[identity] = {'key': name, 'type': kind, 'required': required, 'size': size, 'status': 'available'}
        self.db.create_string_attribute.side_effect = lambda d,c,k,s,r: store(c,k,'string',r,s)
        self.db.create_integer_attribute.side_effect = lambda d,c,k,r,**kw: store(c,k,'integer',r)
        self.db.create_datetime_attribute.side_effect = lambda d,c,k,r: store(c,k,'datetime',r)
        self.db.create_boolean_attribute.side_effect = lambda d,c,k,r: store(c,k,'boolean',r)
        self.db.get_attribute.side_effect = lambda d,c,k: self.fields[(c,k)]
        def index(d,c,k,t,attrs):
            if (c,k) in self.indexes: raise AppwriteException('duplicate',409)
            self.indexes[(c,k)] = {'key': k, 'type': t, 'attributes': attrs, 'status': 'available'}
        self.db.create_index.side_effect = index
        def get_index(d,c,k):
            if (c,k) not in self.indexes: raise AppwriteException('Not found',404)
            return self.indexes[(c,k)]
        self.db.get_index.side_effect = get_index

    def test_idempotent_private_storage_and_indexes(self):
        migrate(self.db, 'db', 'devices'); migrate(self.db, 'db', 'devices')
        self.assertEqual(len(self.indexes), 4)
        self.assertEqual(self.fields[('controller_activity_events', 'payload')]['size'], 8192)
        self.assertFalse(self.fields[('devices', 'controller_id')]['required'])
        for call in self.db.create_collection.call_args_list:
            self.assertEqual(call.kwargs['permissions'], [])
            self.assertFalse(call.kwargs['document_security'])

    def test_public_and_incompatible_storage_are_rejected(self):
        self.db.get_collection.return_value = {'$permissions': ['read("any")']}
        with self.assertRaises(RuntimeError): migrate(self.db, 'db', 'devices')
        self.db.get_collection.return_value = {'$permissions': []}
        migrate(self.db, 'db', 'devices')
        self.fields[('controller_activity_events', 'payload')]['size'] = 10
        with self.assertRaises(RuntimeError): migrate(self.db, 'db', 'devices')

if __name__ == '__main__': unittest.main()
