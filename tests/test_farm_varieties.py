import json
import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from farm_varieties import farm_variety_assignment, assigned_batch_variety
from routes import r2_farms as farms, r5_batches as batches


class FarmVarietyRouteTests(unittest.TestCase):
    def setUp(self):
        self.actor = {'$id': 'admin', 'role': 'admin'}
        self.plant = {'$id': 'p', 'name': 'Lettuce', 'status': 'active'}
        self.crops = {'a': {'$id': 'a', 'plant_type_ID': 'p', 'variety_name': 'Batavia'},
                      'b': {'$id': 'b', 'plant_type_ID': 'p', 'variety_name': 'Lollo Rosso'},
                      'c': {'$id': 'c', 'plant_type_ID': 'tomato', 'variety_name': 'Roma'},
                      'd': {'$id': 'd', 'plant_type_ID': 'p', 'variety_name': 'Green'}}
        self.farm = {'$id': 'f', 'name': 'Farm', 'plant_type': 'Lettuce', 'plant_type_ID': 'p',
                     'plant_variety': 'Batavia', 'crop_variety_ids': ['a', 'b'],
                     'plant_varieties': ['Batavia', 'Lollo Rosso'], 'caretakerID': 'care'}
        self.batch = {'$id': 'batch', 'farmID': 'f', 'plant_type_ID': 'p', 'plant_name': 'Lettuce',
                      'plant_variety': 'Batavia', 'crop_variety_id': 'a', 'production_status': 'Growing'}
        app = FastAPI(); app.include_router(farms.collection2_router); app.include_router(batches.collection5_router)
        app.dependency_overrides[farms.current_member] = lambda: self.actor
        self.client = TestClient(app); self.addCleanup(self.client.close)
        self.db = Mock()
        def get(*args, **kw):
            identity = kw.get('document_id') or args[2]
            return {'f': self.farm, 'p': self.plant, 'care': {'name': 'Caretaker', 'role': 'caretaker', 'status': 'Active'},
                    'batch': self.batch, **self.crops}[identity]
        self.db.get_document.side_effect = get
        self.db.list_documents.return_value = {'documents': [], 'total': 0}
        self.db.create_document.side_effect = lambda **kw: {'$id': 'created', **kw['data']}
        self.db.update_document.side_effect = lambda **kw: {'$id': 'updated', **kw['data']}
        for route in [farms, batches]:
            patch.object(route, 'db', self.db).start(); patch.object(route, 'write_audit').start()
        patch.object(batches, 'st').start(); self.addCleanup(patch.stopall)
        self.data = dict(name='Farm', location='Accra', ownerID='owner', caretakerID='care',
                         plant_type='Lettuce', plant_variety='Batavia', status='Active', tier_type='Compact')
        self.batch_data = dict(batch_no='B', farmID='f', farm_name='Farm', plant_type_ID='p',
            plant_name='Lettuce', plant_variety='Lollo Rosso', crop_variety_id='b', farm_manager_id='manager',
            farm_manager_name='Manager', start_date='2026-10-08', end_date='2026-11-08',
            total_seeds_nursed='100', created_by='admin')

    def test_create_farm_keeps_two_variety_ids_and_legacy_primary(self):
        response = self.client.post('/farms/info', data={**self.data, 'plant_type_ID': 'p', 'crop_variety_ids': '["a","b","a"]'})
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.db.create_document.call_args.kwargs['data']
        self.assertEqual(saved['crop_variety_ids'], ['a', 'b'])
        self.assertEqual(saved['plant_varieties'], ['Batavia', 'Lollo Rosso'])
        self.assertEqual(saved['plant_variety'], 'Batavia')

    def test_update_replaces_selection_and_status_update_preserves_selection(self):
        response = self.client.put('/farms/f', data={**self.data, 'crop_variety_ids': '["b"]', 'plant_type_ID': 'p'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['user']['plant_variety'], 'Lollo Rosso')
        response = self.client.put('/farms/f', data={**self.data, 'status': 'Suspended'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('crop_variety_ids', self.db.update_document.call_args.kwargs['data'])

    def test_invalid_empty_deleted_and_wrong_parent_selections_do_not_write(self):
        for raw in ['[]', '{}', '[null]', '["missing"]', '["c"]']:
            response = self.client.put('/farms/f', data={**self.data, 'plant_type_ID': 'p', 'crop_variety_ids': raw})
            self.assertEqual(response.status_code, 422, response.text)
        self.db.update_document.assert_not_called()
        self.actor['role'] = 'caretaker'
        self.assertEqual(self.client.put('/farms/f', data={**self.data, 'crop_variety_ids': '["a"]'}).status_code, 403)

    def test_old_client_cannot_overwrite_multiple_selection_with_single_value(self):
        response = self.client.put('/farms/f', data={**self.data, 'plant_variety': 'Green'})
        self.assertEqual(response.status_code, 422, response.text)
        self.db.update_document.assert_not_called()

    def test_new_batches_choose_either_assigned_variety_and_reject_unassigned(self):
        response = self.client.post('/batches/info', data=self.batch_data)
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.db.create_document.call_args.kwargs['data']
        self.assertEqual(saved['crop_variety_id'], 'b'); self.assertEqual(saved['plant_variety'], 'Lollo Rosso')
        self.db.create_document.reset_mock()
        for identity in ['c', 'd']:
            response = self.client.post('/batches/info', data={**self.batch_data, 'crop_variety_id': identity})
            self.assertEqual(response.status_code, 422, response.text)
        self.db.create_document.assert_not_called()

    def test_batch_variety_edits_validate_assignment_but_historical_notes_still_save(self):
        response = self.client.put('/batches/batch', data={'plant_variety': 'Green', 'crop_variety_id': 'd'})
        self.assertEqual(response.status_code, 422, response.text)
        self.farm['crop_variety_ids'] = ['b']
        response = self.client.put('/batches/batch', data={'plant_variety': 'Batavia', 'technical_issues': 'Notes'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('crop_variety_id', self.db.update_document.call_args.kwargs['data'])

    def test_renaming_catalog_variety_retains_id_and_canonical_batch_label(self):
        self.crops['b']['variety_name'] = 'Lollo Rosso Updated'
        response = self.client.post('/batches/info', data=self.batch_data)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.create_document.call_args.kwargs['data']['plant_variety'], 'Lollo Rosso Updated')


class FarmVarietyCompatibilityTests(unittest.TestCase):
    def test_legacy_unambiguous_name_and_inactive_existing_link(self):
        plant = {'$id': 'p', 'name': 'Lettuce', 'status': 'active'}
        crop = {'variety_name': 'Green', 'crop_name': 'Lettuce'}
        link = farm_variety_assignment('["a"]', '', 'Lettuce', '', {}, lambda _: plant, lambda _: crop, lambda: [plant])
        self.assertEqual(link['crop_variety_ids'], ['a'])
        plant['status'] = 'inactive'
        self.assertEqual(farm_variety_assignment('["a"]', 'p', 'Lettuce', 'Green', link, lambda _: plant, lambda _: crop, lambda: [plant])['plant_type_ID'], 'p')
        self.assertEqual(assigned_batch_variety({}, 'p', 'Lettuce', 'Green', '', lambda _: crop), {})
