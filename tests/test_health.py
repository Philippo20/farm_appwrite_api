"""Exercise liveness without importing Appwrite or database configuration."""
import ast
from pathlib import Path
import unittest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


class HealthTests(unittest.TestCase):
    def test_health_is_async_public_and_uncached(self):
        tree = ast.parse(Path('server.py').read_text())
        handler = next(node for node in tree.body
                       if isinstance(node, ast.AsyncFunctionDef)
                       and node.name == 'health_check')
        handler.decorator_list = []
        scope = {'JSONResponse': JSONResponse}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), 'server.py', 'exec'), scope)
        app = FastAPI()
        app.get('/health')(scope['health_check'])
        response = TestClient(app).get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'service': 'farmestates-api'})
        self.assertEqual(response.headers['cache-control'], 'no-store')
