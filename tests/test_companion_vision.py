import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

class VisionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('companion_vision'), 'local vision boundary must exist')
        import companion_vision as vision
        self.v = vision
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = Path(self.tmp.name) / 'config.json'
        self.patch = patch.object(vision, 'CONFIG_PATH', self.cfg)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        app = FastAPI()
        app.include_router(vision.router)
        self.client = TestClient(app, base_url='http://127.0.0.1:3787', client=('127.0.0.1', 50000))
        self.app = app
        self.png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jVxkAAAAASUVORK5CYII='

    def config(self, endpoint='http://localhost:11434/v1', model='vision'):
        return self.client.post('/api/companion/vision/config', json={'endpoint': endpoint, 'model': model})

    def test_forbidden_endpoints(self):
        for endpoint in ['https://example.com/v1','http://192.168.1.1/v1','http://2130706433/v1','http://127.0.0.1.evil.test/v1','http://user@localhost/v1','http://localhost/v1?x=1','http://localhost/v1#x','file:///tmp/model','http://[::ffff:127.0.0.1]/v1']:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.config(endpoint).status_code, 422)
        self.assertFalse(self.cfg.exists())

    def test_config_only_persists_endpoint_model(self):
        self.assertEqual(self.config().status_code, 200)
        self.assertEqual(json.loads(self.cfg.read_text()), {'endpoint':'http://127.0.0.1:11434/v1','model':'vision'})
        self.assertEqual(self.client.post('/api/companion/vision/config',json={'endpoint':'http://localhost/v1','model':'x','image':self.png}).status_code,422)

    def test_origin_and_host_boundary(self):
        remote = TestClient(self.app, base_url='http://127.0.0.1:3787', client=('192.168.1.50',50000))
        self.assertEqual(remote.get('/api/companion/vision/status').status_code,403)
        for headers in [{'Origin':'https://evil.test'},{'Host':'evil.test'},{'Origin':'null'},{'Origin':'http://localhost:8888'}]:
            self.assertEqual(self.client.post('/api/companion/vision/test',headers=headers).status_code,403)
        with patch.object(self.v,'request_json',return_value={'data':[]}):
            self.assertEqual(self.client.get('/api/companion/vision/status',headers={'Origin':'http://localhost:3787'}).status_code,200)

    def test_selected_model_required_no_fallback(self):
        self.config(model='missing')
        with patch.object(self.v,'request_json',return_value={'data':[{'id':'another'}]}):
            result=self.client.post('/api/companion/vision/test').json()
            self.assertFalse(result['available'])
            self.assertEqual(result['model'],'missing')
            self.assertEqual(result['models'],['another'])

    def test_analyze_and_transient_image(self):
        self.config()
        def response(endpoint, path, payload=None, timeout=3):
            self.assertEqual(endpoint,'http://127.0.0.1:11434/v1')
            self.assertEqual(path,'chat/completions')
            self.assertEqual(timeout,20)
            self.assertEqual(payload['model'],'vision')
            self.assertEqual(payload['messages'][1]['content'][1]['image_url']['url'],self.png)
            return {'choices':[{'message':{'content':'You are organizing your workspace.'}}]}
        with patch.object(self.v,'request_json',side_effect=response):
            result=self.client.post('/api/companion/vision/analyze',json={'image':self.png,'context':'Workspace'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['model'],'vision')
        self.assertNotIn('image',self.cfg.read_text())

    def test_invalid_and_oversize_images(self):
        self.config()
        for image in ['data:image/png;base64,!!!','data:image/jpeg;base64,'+base64.b64encode(b'not jpeg').decode(),'data:image/svg+xml;base64,AAAA','data:image/png;base64,'+'A'*2800000]:
            self.assertEqual(self.client.post('/api/companion/vision/analyze',json={'image':image}).status_code,422)

    def test_one_inflight(self):
        self.config()
        with self.v.ANALYZE_LOCK:
            self.assertEqual(self.client.post('/api/companion/vision/analyze',json={'image':self.png}).status_code,429)

    def test_transport_disables_proxy_and_redirects(self):
        opener=self.v.build_local_opener()
        import urllib.request
        self.assertFalse(any(isinstance(h,urllib.request.ProxyHandler) and h.proxies for h in opener.handlers))
        redirect=next(h for h in opener.handlers if isinstance(h,urllib.request.HTTPRedirectHandler))
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError):
            redirect.redirect_request(None,None,302,'redirect',{},'https://example.com')

if __name__=='__main__': unittest.main()
