import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import io

import httpx

from app.config import Settings
from app.provider import Provider, ProviderError
from scripts.configure import address, main as configure
from app.security import verify_password


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def make_provider(self, handler, **settings):
        provider = Provider(Settings(api_key='test-key', **settings))
        await provider.client.aclose()
        provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(provider.close)
        return provider

    async def test_openai_compatible_stream(self):
        def handler(request):
            self.assertEqual(request.headers['authorization'], 'Bearer test-key')
            self.assertEqual(request.url.path, '/v1/chat/completions')
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n')
        provider = await self.make_provider(handler)
        self.assertEqual([chunk async for chunk in provider.chat([], 'test')], ['hello'])

    async def test_truncated_stream_is_an_error(self):
        provider = await self.make_provider(lambda request: httpx.Response(200, text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'))
        with self.assertRaises(ProviderError):
            _ = [chunk async for chunk in provider.chat([], 'test')]

    async def test_upstream_secrets_are_not_exposed_in_errors(self):
        provider = await self.make_provider(lambda request: httpx.Response(401, text='secret-provider-payload'))
        with self.assertRaises(ProviderError) as raised:
            _ = [chunk async for chunk in provider.chat([], 'test')]
        self.assertNotIn('secret-provider-payload', str(raised.exception))

    async def test_missing_api_key(self):
        provider = Provider(Settings(api_key=''))
        self.addAsyncCleanup(provider.close)
        with self.assertRaises(ProviderError):
            _ = [chunk async for chunk in provider.chat([], 'test')]


class SetupTests(unittest.TestCase):
    def test_configuration_keeps_password_hashed_and_file_private(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / '.env'
            answers = ['ai.example.com', 'owner', '', '', '', '']
            passwords = ['example-long-password', 'example-long-password', 'test-api-key', '']
            with patch('sys.argv', ['configure.py', str(destination)]), patch('builtins.input', side_effect=answers), patch('getpass.getpass', side_effect=passwords), patch('sys.stdout', new=io.StringIO()):
                configure()
            contents = destination.read_text()
            self.assertNotIn('example-long-password', contents)
            self.assertIn("COOKIE_SECURE='true'", contents)
            encoded = next(line.split('=', 1)[1].strip("'") for line in contents.splitlines() if line.startswith('ADMIN_PASSWORD_HASH='))
            self.assertTrue(verify_password('example-long-password', encoded))
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_ip_domain_and_ipv6_configuration(self):
        self.assertEqual(address('203.0.113.2'), ('http://:80', 'http://203.0.113.2', 'false'))
        self.assertEqual(address('https://ai.example.com/'), ('ai.example.com', 'https://ai.example.com', 'true'))
        self.assertEqual(address('2001:db8::1'), ('http://:80', 'http://[2001:db8::1]', 'false'))
        for value in ['https://bad/path', 'host:8000', 'bad host', '*.example.com']:
            with self.assertRaises(ValueError):
                address(value)
