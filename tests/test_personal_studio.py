"""Personal mode needs no Studio account; public callbacks cannot expose content."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from studio import auth
from studio.store import Store
from api import studio, publications


class PersonalStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, STUDIO_DATA_DIR=self.temp,
            STUDIO_AUTH_ENABLED='0', STUDIO_LOCAL_ONLY='1', STUDIO_LOCAL_DOCKER='0',
            STUDIO_PUBLIC_MODE='0', STUDIO_PUBLIC_URL='https://studio.example'))
        self.store = Store()
        self.enterContext(patch.object(studio, 'get_store', return_value=self.store))
        self.app = FastAPI()
        self.app.middleware('http')(auth.middleware)
        self.app.include_router(auth.router)
        self.app.include_router(studio.router)
        self.app.include_router(publications.router)
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8001', client=('127.0.0.1', 45000))
        self.product = {'name': 'Hộp bút', 'uses': 'Đựng bút', 'price': '20.000đ',
                        'product_link': 'https://example.com/p'}

    def test_no_setup_or_credentials_needed_to_create_and_reopen_session(self):
        status = self.client.get('/api/v2/auth/me').json()
        self.assertFalse(status['enabled'])
        self.assertFalse(status['setup_required'])
        created = self.client.post('/api/v2/sessions', json=self.product)
        self.assertEqual(created.status_code, 201, created.text)
        again = TestClient(self.app, base_url='http://127.0.0.1:8001', client=('127.0.0.1', 45001))
        self.assertEqual(again.get('/api/v2/sessions').json()[0]['id'], created.json()['id'])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 0)

    def test_old_account_pages_redirect_and_account_mutations_are_unavailable(self):
        for path in ('/login', '/account'):
            r = self.client.get(path, follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertEqual(r.headers['location'], '/app')
        for action in ('setup', 'register', 'login', 'recover', 'password', 'logout'):
            self.assertEqual(self.client.post('/api/v2/auth/' + action, json={}).status_code, 404)

    def test_public_or_forwarded_requests_cannot_read_or_change_sessions(self):
        public = TestClient(self.app, base_url='https://studio.example', client=('203.0.113.2', 45000))
        for path in ('/app', '/api/v2/sessions', '/api/v2/auth/me', '/api/v2/tiktok/accounts'):
            self.assertEqual(public.get(path).status_code, 403)
        self.assertEqual(self.client.get('/api/v2/sessions', headers={'X-Forwarded-For': '203.0.113.2'}).status_code, 403)
        rebound = TestClient(self.app, base_url='http://attacker.example:8001', client=('127.0.0.1', 45000))
        self.assertEqual(rebound.get('/api/v2/sessions').status_code, 403)

    def test_cross_site_write_is_blocked_without_an_account(self):
        for headers in ({'Origin': 'https://evil.invalid'}, {'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.client.post('/api/v2/sessions', json=self.product, headers=headers).status_code, 403)
        self.assertEqual(self.client.post('/api/v2/sessions', json=self.product,
            headers={'Origin': 'http://127.0.0.1:8001'}).status_code, 201)

    def test_docker_local_port_works_but_forwarded_editor_remains_blocked(self):
        docker = TestClient(self.app, base_url='http://127.0.0.1:8001', client=('172.18.0.1', 45000))
        self.assertEqual(docker.get('/api/v2/sessions').status_code, 403)
        with patch.dict(os.environ, STUDIO_LOCAL_DOCKER='1'):
            self.assertEqual(docker.get('/api/v2/sessions').status_code, 200)
            self.assertEqual(docker.get('/api/v2/sessions', headers={'X-Forwarded-For': '203.0.113.2'}).status_code, 403)

    def test_tiktok_uses_local_identity_and_callback_links_back_to_local_app(self):
        with patch.object(publications, 'call', return_value={'url': 'https://www.tiktok.com/'}) as call:
            self.assertEqual(self.client.post('/api/v2/tiktok/accounts/connect').status_code, 200)
            call.assert_called_once_with('/owners/local/connect', 'POST')
        public = TestClient(self.app, base_url='https://studio.example', client=('203.0.113.2', 45000))
        with patch.object(publications, 'call', return_value={}) as call:
            result = public.get('/api/v2/tiktok/callback?state=synthetic-state&code=synthetic-code')
            self.assertEqual(result.status_code, 200)
            self.assertIn('http://127.0.0.1:8001/app', result.text)
            self.assertNotIn('synthetic-code', result.text)
            call.assert_called_once_with('/callback', 'POST', {'state': 'synthetic-state', 'code': 'synthetic-code'})
        self.assertEqual(public.get('/api/v2/tiktok/callback').status_code, 400)


if __name__ == '__main__':
    unittest.main()
