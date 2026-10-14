import unittest
from unittest.mock import Mock, patch
from appwrite.exception import AppwriteException
from migrate_command_devices import migrate, ensure_controls

class CommandMigrationTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.client._endpoint = 'https://example.test/v1'
        self.db.client._global_headers = {}
        self.enum = {'status': 'available', 'elements': ['temperature', 'VPD', 'light_switch'], 'required': True, 'default': None}
        self.field = {'status': 'available', 'type': 'string', 'size': 8192, 'required': False, 'array': False}
        self.db.get_attribute.side_effect = lambda database, collection, name: self.enum if name == 'sensortype' else self.field

    def test_preserves_existing_types_required_and_explicit_null_default(self):
        def update(url, **kwargs):
            self.assertEqual(kwargs['json'], {'elements': ['temperature', 'VPD', 'light_switch', 'command_device'],
                                               'required': True, 'default': None})
            self.enum['elements'] = kwargs['json']['elements']
            return Mock(ok=True)
        with patch('migrate_command_devices.requests.patch', side_effect=update) as request:
            migrate(self.db, 'database', 'devices')
        request.assert_called_once()
        self.db.create_string_attribute.assert_called_once_with('database', 'devices', 'command_config', 8192, False)

    def test_repeated_migration_is_idempotent_but_rejects_a_wrong_existing_schema(self):
        self.enum['elements'].append('command_device')
        self.db.create_string_attribute.side_effect = AppwriteException('Exists', 409)
        with patch('migrate_command_devices.requests.patch') as request:
            migrate(self.db, 'database', 'devices')
        request.assert_not_called()
        self.field['array'] = True
        with self.assertRaises(RuntimeError): migrate(self.db, 'database', 'devices')

    def test_reuses_a_compatible_existing_control_index_under_another_name(self):
        self.db.get_attribute.side_effect = lambda *args: {'status': 'available', 'type': 'string',
            'size': 8192, 'required': True, 'array': False}
        self.db.list_indexes.return_value = {'indexes': [{'key': 'existing-index', 'type': 'key',
            'attributes': ['sensor_id', 'kind'], 'status': 'available'}]}
        error = AppwriteException('There is already an index with the same attributes and orders', 400)
        with patch('migrate_command_devices.create_control_collection', side_effect=error):
            ensure_controls(self.db, 'database', 'controls')
        self.db.list_indexes.return_value = {'indexes': []}
        with patch('migrate_command_devices.create_control_collection', side_effect=error), self.assertRaises(RuntimeError):
            ensure_controls(self.db, 'database', 'controls')
