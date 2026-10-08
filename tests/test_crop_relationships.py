import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from crop_relationships import exact_legacy_plant, crop_plant_link, variety_matches_plant
from routes import r16_crops as crops


class CropRelationshipTests(unittest.TestCase):
    def test_exact_unique_legacy_match_only(self):
        plant = {'$id': 'p', 'name': 'Lettuce'}
        self.assertEqual(exact_legacy_plant({'crop_name': ' LETTUCE '}, [plant]), plant)
        self.assertIsNone(exact_legacy_plant({'crop_name': 'Lettuce'}, [plant, {**plant, '$id': 'other'}]))
        self.assertIsNone(exact_legacy_plant({'crop_name': 'Lettuce'}, [{**plant, 'name': 'Red Lettuce'}]))
        self.assertIsNone(exact_legacy_plant({'crop_name': 'Lettuce'}, [{**plant, 'is_category': True}]))

    def test_parent_id_survives_rename_and_prevents_cross_plant_match(self):
        plant = {'$id': 'p', 'name': 'New Lettuce Name', 'status': 'active'}
        self.assertEqual(crop_plant_link('p', 'Old name', lambda _: plant, lambda: [])['crop_name'], 'New Lettuce Name')
        crop = {'plant_type_ID': 'p', 'crop_name': 'Tomato'}
        self.assertTrue(variety_matches_plant(crop, 'p', 'Lettuce'))
        self.assertFalse(variety_matches_plant(crop, 'other', 'Tomato'))

    def test_invalid_category_and_new_inactive_parent_rejected(self):
        for plant in [{'name': 'Lettuce', 'is_category': True}, {'name': 'Lettuce', 'status': 'inactive'}]:
            with self.assertRaises(HTTPException): crop_plant_link('p', '', lambda _: plant, lambda: [])
        with self.assertRaises(HTTPException): crop_plant_link('', 'Unknown', lambda _: {}, lambda: [])
        plant = {'name': 'Lettuce', 'status': 'inactive'}
        self.assertEqual(crop_plant_link(None, '', lambda _: plant, lambda: [], {'plant_type_ID': 'p'})['plant_type_ID'], 'p')


class CropLinkRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(crops.collection16_router)
        self.client = TestClient(app); self.addCleanup(self.client.close)
        self.db = patch.object(crops, 'db').start(); self.storage = patch.object(crops, 'st').start()
        patch.object(crops, 'write_audit').start(); self.addCleanup(patch.stopall)
        self.plant = {'$id': 'p', 'name': 'Lettuce', 'status': 'active'}
        self.old = {'$id': 'c', 'crop_name': 'Old crop label', 'variety_name': 'Batavia'}
        def get(*args, **kwargs):
            collection = kwargs.get('collection_id') or args[1]
            return self.plant if collection == crops.db_collection_id3 else self.old
        self.db.get_document.side_effect = get
        self.db.create_document.side_effect = lambda **kwargs: {'$id': 'c', **kwargs['data']}
        self.db.update_document.side_effect = lambda **kwargs: {'$id': 'c', **kwargs['data']}
        self.storage.create_file.return_value = {'$id': 'image'}
        self.data = dict(crop_name='Label', variety_name='Batavia', plant_type_ID='p', plant_duration_value='30',
                        plant_duration_unit='days', harvesting_weight='1', company='Seed Co', sprouting_ratio='90',
                        ec_level_min='1', ec_level_max='2', ph_level_min='5', ph_level_max='7', temp_min='18', temp_max='25',
                        humidity_min='40', humidity_max='70', created_by='admin')

    def test_new_variety_stores_parent_before_uploading(self):
        response = self.client.post('/crops/info', data=self.data, files={'crop_image': ('crop.png', b'image', 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.db.create_document.call_args.kwargs['data']
        self.assertEqual(saved['plant_type_ID'], 'p'); self.assertEqual(saved['crop_name'], 'Lettuce')
        self.assertEqual(saved['variety_name'], 'Batavia')

    def test_edit_links_existing_variety_without_replacing_image(self):
        response = self.client.put('/crops/info/c', data={'plant_type_ID': 'p', 'crop_name': 'Label'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['updated_fields'], {'plant_type_ID': 'p', 'crop_name': 'Lettuce'})
        self.storage.create_file.assert_not_called()

    def test_invalid_parent_fails_before_storage_or_document_write(self):
        self.plant['is_category'] = True
        response = self.client.post('/crops/info', data=self.data, files={'crop_image': ('crop.png', b'image', 'image/png')})
        self.assertEqual(response.status_code, 422)
        self.storage.create_file.assert_not_called(); self.db.create_document.assert_not_called()

    def test_crop_list_loads_every_page(self):
        pages = [[{'$id': str(i), 'crop_image_url': 'https://example.test/a.png'} for i in range(100)],
                 [{'$id': '100', 'crop_image_url': 'https://example.test/a.png'}]]
        self.db.list_documents.side_effect = [{'documents': p} for p in pages]
        response = self.client.get('/crops')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['count'], 101)
