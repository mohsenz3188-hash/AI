import base64
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.provider import ProviderError
from app.security import hash_password, verify_password

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class FakeProvider:
    fail = False
    captured = None
    invalid_image = False

    async def chat(self, messages, model):
        self.captured = (messages, model)
        yield "سلام "
        if self.fail:
            raise ProviderError("مدل در دسترس نیست.")
        yield "دنیا\n```python\nprint('hello')\n```"

    async def image(self, prompt, size):
        return base64.b64encode(b'<html>bad</html>' if self.invalid_image else PNG).decode()

    async def close(self):
        pass


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("test-password-1234")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.provider = FakeProvider()
        cfg = Settings(data_dir=Path(self.temp.name), password_hash=self.password_hash, origins=("http://testserver",), api_key="test-only", image_key="test-only", models=("test-model",))
        self.client = TestClient(create_app(cfg, self.provider))
        self.client.__enter__()
        self.client.headers['origin'] = 'http://testserver'

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def login(self):
        response = self.client.post('/api/login', json={'username': 'admin', 'password': 'test-password-1234'})
        self.assertEqual(response.status_code, 200)
        return response

    def new(self):
        return self.client.post('/api/conversations').json()['id']

    def chat(self, cid, **overrides):
        return self.client.post(f'/api/conversations/{cid}/chat', json={'message': 'یک برنامه بنویس', 'model': 'test-model', **overrides})

    def test_authentication_csrf_and_logout(self):
        self.assertEqual(self.client.get('/api/config').status_code, 401)
        self.assertEqual(self.client.post('/api/login', headers={'origin': 'https://attacker.invalid'}, json={'username': 'admin', 'password': 'test-password-1234'}).status_code, 403)
        response = self.login()
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])
        cfg = self.client.get('/api/config')
        self.assertNotIn('test-only', cfg.text)
        self.assertIn("script-src 'self'", cfg.headers['content-security-policy'])
        self.assertEqual(cfg.headers['cache-control'], 'no-store')
        old_token = self.client.cookies.get('nava_session')
        self.assertEqual(self.client.post('/api/logout').status_code, 200)
        self.client.cookies.set('nava_session', old_token)
        self.assertEqual(self.client.get('/api/config').status_code, 401)

    def test_bad_password_and_login_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/api/login', json={'username': 'admin', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.client.post('/api/login', json={'username': 'admin', 'password': 'wrong'}).status_code, 429)

    def test_chat_history_attachments_export_and_delete(self):
        self.login()
        cid = self.new()
        response = self.chat(cid, mode='code', language='日本語', attachments=[{'name': 'demo.rs', 'text': 'fn main() {}'}])
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[-1]['type'], 'done')
        messages, model = self.provider.captured
        self.assertIn('日本語', messages[0]['content'])
        self.assertIn('fn main()', messages[-1]['content'])
        self.assertEqual(model, 'test-model')
        conv = self.client.get(f'/api/conversations/{cid}').json()
        self.assertEqual(len(conv['messages']), 2)
        self.assertEqual(conv['title'], 'یک برنامه بنویس')
        self.chat(cid, message='بهترش کن')
        self.assertEqual(len(self.provider.captured[0]), 4)
        self.assertEqual(self.client.patch(f'/api/conversations/{cid}', json={'title': 'برنامهٔ من'}).status_code, 200)
        exported = self.client.get(f'/api/conversations/{cid}/export')
        self.assertIn('برنامهٔ من', exported.text)
        self.assertIn('attachment', exported.headers['content-disposition'])
        self.assertEqual(self.client.delete(f'/api/conversations/{cid}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/conversations/{cid}').status_code, 404)

    def test_provider_failure_does_not_save_partial_history_and_allows_retry(self):
        self.login()
        cid = self.new()
        self.provider.fail = True
        events = [json.loads(line) for line in self.chat(cid).text.splitlines()]
        self.assertEqual(events[-1]['type'], 'error')
        self.assertEqual(self.client.get(f'/api/conversations/{cid}').json()['messages'], [])
        self.provider.fail = False
        self.assertEqual(json.loads(self.chat(cid).text.splitlines()[-1])['type'], 'done')

    def test_validation_model_body_and_attachment_limits(self):
        self.login()
        cid = self.new()
        self.assertEqual(self.chat(cid, model='unlisted-model').status_code, 422)
        self.assertEqual(self.chat(cid, message='   ').status_code, 422)
        self.assertEqual(self.chat(cid, mode='shell').status_code, 422)
        self.assertEqual(self.chat(cid, attachments=[{'name': 'a', 'text': 'x'*20000}]*3).status_code, 422)
        self.assertEqual(self.client.post('/api/conversations', content=b'x'*270000).status_code, 413)

    def test_images_are_saved_protected_and_deleted(self):
        self.login()
        response = self.client.post('/api/images', json={'prompt': 'کوهستان'})
        self.assertEqual(response.status_code, 201)
        iid = response.json()['id']
        self.assertEqual(self.client.get(f'/api/images/{iid}/file').content, PNG)
        self.assertEqual(len(self.client.get('/api/images').json()), 1)
        self.client.post('/api/logout')
        self.assertEqual(self.client.get(f'/api/images/{iid}/file').status_code, 401)
        self.login()
        self.assertEqual(self.client.delete(f'/api/images/{iid}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/images/{iid}/file').status_code, 404)
        self.provider.invalid_image = True
        self.assertEqual(self.client.post('/api/images', json={'prompt': 'test'}).status_code, 502)
        self.assertEqual(self.client.get('/api/images').json(), [])

    def test_static_and_health(self):
        self.assertEqual(self.client.get('/healthz').json(), {'status': 'ok'})
        self.assertIn('lang="fa"', self.client.get('/').text)
        self.assertEqual(self.client.get('/static/app.js').status_code, 200)
        self.assertEqual(self.client.get('/.env').status_code, 404)

    def test_password_hashing(self):
        self.assertTrue(verify_password('test-password-1234', self.password_hash))
        self.assertFalse(verify_password('wrong', self.password_hash))
        self.assertFalse(verify_password('anything', 'malformed'))


if __name__ == '__main__':
    unittest.main()
