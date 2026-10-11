import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from farm_purchase import accepted, capture_purchase, choose_price, make_snapshot, receipt_identity, value_unpriced_receipts

MAIN = types.SimpleNamespace(db_id='db', db_collection_id2='farms', db_collection_id5='batches',
                             db_collection_id7='receipts', db_collection_id17='prices')
PRICE = {'$id': 'price', 'pricing_type': 'hub_purchase', 'farm_id': 'farm', 'farm_name': 'East',
         'plant_type': 'Lettuce', 'crop_variety': 'Batavia', 'status': 'Active', 'unit': 'kg',
         'regular_price': 10, 'bulk_price': 7.5, 'owner_price_tier': 'Bulk'}
RECEIPT = {'$id': 'receipt', 'farm_name': 'East', 'plant_type': 'Lettuce', 'plant_variety': 'Batavia',
           'batch_number': 'B-1', 'total_weight': 12.5, 'total_heads': 50, 'delivery_status': 'Delivered'}
BATCH = {'$id': 'batch', 'batch_no': 'B-1', 'farmID': 'farm', 'farm_name': 'East',
         'plant_name': 'Lettuce', 'plant_variety': 'Batavia'}

class PurchaseTests(unittest.TestCase):
    def setUp(self):
        self.identity = receipt_identity(RECEIPT, BATCH)

    def test_batch_farm_id_and_bulk_rate_drive_revenue(self):
        snapshot = make_snapshot(RECEIPT, self.identity, PRICE)
        self.assertEqual(snapshot['farm_id'], 'farm')
        self.assertEqual(snapshot['price_tier'], 'Bulk')
        self.assertEqual(snapshot['total_amount'], 93.75)
        self.assertEqual(snapshot['unit_price'], 7.5)

    def test_regular_default_rounds_cedi_and_converts_units(self):
        for unit, rate, quantity, expected in [('kg', 1.234, 12.5, 15.43),
                                               ('g', .002, 12500, 25), ('heads', 2, 50, 100)]:
            snapshot = make_snapshot(RECEIPT, self.identity,
                {**PRICE, 'owner_price_tier': None, 'unit': unit, 'regular_price': rate})
            self.assertEqual(snapshot['quantity'], quantity)
            self.assertEqual(snapshot['total_amount'], expected)

    def test_price_selection_never_uses_hub_sale_other_farm_or_variety(self):
        for change in [{'farm_id': 'other'}, {'crop_variety': 'Lollo'},
                       {'plant_type': 'Basil'}, {'pricing_type': 'hub_sale'}, {'status': 'Inactive'}]:
            self.assertIsNone(choose_price(self.identity, [{**PRICE, **change}]))
        self.assertEqual(choose_price(self.identity, [PRICE])['$id'], 'price')
        self.assertIsNone(choose_price(self.identity, [PRICE, {**PRICE, '$id': 'duplicate'}]))
        fallback = {**PRICE, 'crop_variety': '', '$id': 'general'}
        self.assertEqual(choose_price(self.identity, [fallback, PRICE])['$id'], 'price')

    def test_invalid_rates_quantities_and_unrecorded_units_stay_unpriced(self):
        for change in [{'bulk_price': 0}, {'bulk_price': float('nan')}, {'unit': 'crate'}]:
            self.assertIsNone(make_snapshot(RECEIPT, self.identity, {**PRICE, **change}))
        self.assertIsNone(make_snapshot({**RECEIPT, 'total_weight': 0}, self.identity, PRICE))
        self.assertFalse(accepted({'status': 'Received', 'delivery_status': 'Pending'}))
        self.assertFalse(accepted({**RECEIPT, 'delivery_status': 'Cancelled'}))

    def test_capture_preserves_saved_rates_and_refuses_changed_accepted_quantity(self):
        saved = json.dumps(make_snapshot(RECEIPT, self.identity, PRICE))
        with patch.dict(sys.modules, {'main': MAIN}), patch('farm_purchase.list_all_documents') as reads:
            self.assertEqual(capture_purchase(Mock(), RECEIPT, {**RECEIPT, 'farm_purchase': saved}),
                             {'farm_purchase': saved})
            reads.assert_not_called()
            with self.assertRaises(HTTPException) as error:
                capture_purchase(Mock(), {**RECEIPT, 'total_weight': 13}, {'farm_purchase': saved})
            self.assertEqual(error.exception.status_code, 409)

    def test_capture_resolves_registered_batch_and_active_price(self):
        with patch.dict(sys.modules, {'main': MAIN}), patch('farm_purchase.list_all_documents',
            side_effect=[{'documents': [BATCH]}, {'documents': []}, {'documents': [PRICE]}]):
            snapshot = json.loads(capture_purchase(Mock(), RECEIPT)['farm_purchase'])
        self.assertEqual(snapshot['total_amount'], 93.75)

    def test_explicit_valuation_skips_saved_receipts_other_farms_and_duplicates(self):
        db = Mock()
        saved = json.dumps(make_snapshot(RECEIPT, self.identity, PRICE))
        rows = [{**RECEIPT, 'batch_number': 'old', 'farm_purchase': saved},
                {**RECEIPT, 'batch_number': 'old'}, RECEIPT,
                {**RECEIPT, '$id': 'duplicate'}, {**RECEIPT, 'farm_name': 'Other'}]
        with patch.dict(sys.modules, {'main': MAIN, 'audit_utils': types.SimpleNamespace(write_audit=Mock())}), \
             patch('farm_purchase.list_all_documents', return_value={'documents': rows}), \
             patch('farm_purchase.capture_purchase', return_value={'farm_purchase': saved}) as capture:
            result = value_unpriced_receipts(db, PRICE)
        self.assertEqual(result['valued_receipts'], 1)
        self.assertEqual(capture.call_count, 1)
        self.assertEqual(db.update_document.call_count, 1)

class PricingRouteTests(unittest.TestCase):
    def setUp(self):
        self.db, self.audit = Mock(), Mock()
        self.actor = {'$id': 'actor', 'role': 'admin'}
        spec = importlib.util.spec_from_file_location('pricing_test_routes', Path('routes/r17_pricing.py'))
        self.route = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'main': MAIN, 'db': types.SimpleNamespace(db=self.db),
             'routes.messaging': types.SimpleNamespace(current_member=lambda: self.actor),
             'audit_utils': types.SimpleNamespace(write_audit=self.audit)}):
            spec.loader.exec_module(self.route)
        app = FastAPI(); app.include_router(self.route.collection17_router)
        self.client = TestClient(app); self.addCleanup(self.client.close)
        self.db.create_document.return_value = {'$id': 'price'}
        self.db.get_document.return_value = PRICE
        self.db.update_document.return_value = PRICE
        self.payload = {k: PRICE[k] for k in ['pricing_type', 'farm_id', 'farm_name', 'plant_type',
            'crop_variety', 'unit', 'regular_price', 'bulk_price', 'owner_price_tier', 'status']}

    def test_create_persists_selected_tier_without_auto_pricing_legacy_receipts(self):
        with patch.object(self.route, 'value_unpriced_receipts') as apply:
            result = self.client.post('/pricing/info', data=self.payload)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.db.create_document.call_args.kwargs['data']['owner_price_tier'], 'Bulk')
        apply.assert_not_called()

    def test_update_omitted_tier_preserves_existing_choice(self):
        data = {k: v for k, v in self.payload.items() if k != 'owner_price_tier'}
        self.assertEqual(self.client.put('/pricing/price', data=data).status_code, 200)
        self.assertEqual(self.db.update_document.call_args.kwargs['data']['owner_price_tier'], 'Bulk')

    def test_explicit_existing_receipt_valuation_returns_counts(self):
        with patch.object(self.route, 'value_unpriced_receipts', return_value={'valued_receipts': 3}) as apply:
            result = self.client.post('/pricing/info', data={**self.payload, 'apply_to_unpriced': 'true'})
        self.assertEqual(result.json()['valued_receipts'], 3)
        apply.assert_called_once()

    def test_invalid_tiers_units_and_prices_are_rejected_before_writes(self):
        for change in [{'owner_price_tier': 'Unknown'}, {'regular_price': '-1'},
                       {'bulk_price': 'nan'}, {'unit': 'crate'}, {'bulk_price': '0'}]:
            self.assertEqual(self.client.post('/pricing/info', data={**self.payload, **change}).status_code, 422)
        self.db.create_document.assert_not_called()

    def test_inactive_zero_rate_can_be_saved_but_not_activated(self):
        self.assertEqual(self.client.post('/pricing/info', data={**self.payload,
            'bulk_price': '0', 'status': 'Inactive'}).status_code, 200)
        self.assertEqual(self.client.put('/pricing/price', data={**self.payload,
            'bulk_price': '0'}).status_code, 422)

    def test_purchase_rates_are_admin_only_while_sales_manager_can_manage_hub_sales(self):
        self.actor['role'] = 'sales_manager'
        self.assertEqual(self.client.post('/pricing/info', data=self.payload).status_code, 403)
        self.assertEqual(self.client.put('/pricing/price', data=self.payload).status_code, 403)
        sale = {**self.payload, 'pricing_type': 'hub_sale', 'packaging': 'Tray', 'unit': 'pack'}
        self.assertEqual(self.client.post('/pricing/info', data=sale).status_code, 200)
        self.assertEqual(self.client.put('/pricing/price', data=sale).status_code, 403)
        self.assertEqual(self.client.delete('/pricing/price').status_code, 403)
        self.db.delete_document.assert_not_called()
