import io, os, tempfile, unittest, hashlib, json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
from fastapi.testclient import TestClient
TMP = tempfile.TemporaryDirectory()
os.environ['FIREWATCH_DATA'] = TMP.name
from app.main import app
from app.detector import analyze, Config
from scripts.verify_run import verify
client = TestClient(app)
def png(img): return cv2.imencode('.png', img)[1].tobytes()
class DetectorTests(unittest.TestCase):
    def test_black_no_edges_no_fire(self):
        result,_=analyze(np.zeros((80,80,3),np.uint8))
        self.assertFalse(result['detected']); self.assertEqual(result['area_ratio'],0)
        self.assertTrue(all(x['edge_color_ratio']==0 for x in result['methods']))
    def test_color_region_and_four_methods(self):
        img=np.zeros((100,100,3),np.uint8); img[20:70,20:70]=[0,190,255]
        result,assets=analyze(img)
        self.assertAlmostEqual(result['area_ratio'],0.25)
        self.assertEqual(len(result['boxes']),1)
        self.assertTrue(result['detected']);self.assertEqual(len(result['methods']),4)
        self.assertIn('scharr',assets)
    def test_noise_removed(self):
        img=np.zeros((80,80,3),np.uint8);img[30:32,30:32]=[0,190,255]
        result,_=analyze(img);self.assertEqual(result['boxes'],[])
        self.assertFalse(result['detected'])
    def test_white_is_not_fire(self):
        result,_=analyze(np.full((100,100,3),255,np.uint8));self.assertFalse(result['detected'])
    def test_both_gradient_polarities(self):
        img=np.zeros((100,100,3),np.uint8);img[20:80,20:80]=255
        _,assets=analyze(img)
        self.assertTrue(assets['sobel'][40,19:22].any())
        self.assertTrue(assets['sobel'][40,79:82].any())
    def test_invalid_config(self):
        with self.assertRaises(ValueError):Config(brightness=300)
class ApiTests(unittest.TestCase):
    def test_upload_history_report_images(self):
        img=np.zeros((90,100,3),np.uint8);img[20:70,20:70]=[0,190,255]
        r=client.post('/api/analyze',files={'file':('测试.png',png(img),'image/png')})
        self.assertEqual(r.status_code,200,r.text);data=r.json()
        self.assertTrue(any(x['id']==data['id'] for x in client.get('/api/runs').json()))
        self.assertEqual(client.get('/api/runs/'+data['id']).json(),data)
        self.assertEqual(client.get('/api/runs/'+data['id']+'/report').json(),data)
        for url in data['assets'].values():
            asset=client.get(url);self.assertEqual(asset.status_code,200)
            self.assertIsNotNone(cv2.imdecode(np.frombuffer(asset.content,np.uint8),1))
    def test_invalid_bytes(self):
        r=client.post('/api/analyze',files={'file':('a.png',b'fake','image/png')});self.assertEqual(r.status_code,400)
    def test_missing_file(self):self.assertEqual(client.post('/api/analyze').status_code,422)
    def test_parameter_validation(self):
        for cfg in [{'brightness':-1},{'edge_ratio':1.1},{'min_component':0},{'min_area_ratio':'nan'}]:
            r=client.post('/api/analyze',files={'file':('x.png',png(np.zeros((4,4,3),np.uint8)))},data=cfg)
            self.assertEqual(r.status_code,422)
    def test_large_upload(self):
        r=client.post('/api/analyze',files={'file':('x.png',b'x'*(10*1024*1024+1))});self.assertEqual(r.status_code,413)
    def test_pixel_limit(self):
        out=io.BytesIO();Image.new('RGB',(4000,3100)).save(out,format='PNG')
        self.assertEqual(client.post('/api/analyze',files={'file':('large.png',out.getvalue())}).status_code,400)
    def test_unknown_record_and_asset(self):
        self.assertEqual(client.get('/api/runs/missing').status_code,404)
        self.assertEqual(client.get('/api/runs/missing/images/original').status_code,404)
    def test_static_and_health(self):
        self.assertEqual(client.get('/').status_code,200)
        self.assertEqual(client.get('/api/health').json()['status'],'ok')
    def test_provenance_tracks_source_parameters_and_report(self):
        raw = png(np.zeros((20,20,3),np.uint8))
        def upload(brightness):
            return client.post('/api/analyze',files={'file':('x.png',raw,'image/png')},data={'brightness':brightness}).json()
        first, same, changed = upload(150), upload(150), upload(200)
        p=first['provenance']
        self.assertEqual(p['source_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(p['fingerprint'],same['provenance']['fingerprint'])
        self.assertNotEqual(p['fingerprint'],changed['provenance']['fingerprint'])
        self.assertEqual(verify(Path(TMP.name)/first['id']),[])
    def test_output_verifier_detects_tampering(self):
        raw=png(np.zeros((20,20,3),np.uint8))
        result=client.post('/api/analyze',files={'file':('x.png',raw,'image/png')}).json()
        folder=Path(TMP.name)/result['id']
        (folder/'overlay.png').write_bytes(b'changed')
        self.assertIn('output missing or changed: overlay.png',verify(folder))
    def test_verifier_rejects_manifest_path_escape(self):
        raw=png(np.zeros((20,20,3),np.uint8))
        result=client.post('/api/analyze',files={'file':('x.png',raw,'image/png')}).json()
        folder=Path(TMP.name)/result['id']; report=folder/'report.json'
        result['provenance']['output_sha256']['../outside']='0'*64
        report.write_text(json.dumps(result),encoding='utf-8')
        self.assertIn('invalid output name: ../outside',verify(folder))
    def test_verifier_detects_report_parameter_change(self):
        result=client.post('/api/analyze',files={'file':('x.png',png(np.zeros((20,20,3),np.uint8)),'image/png')}).json()
        folder=Path(TMP.name)/result['id']
        result['config']['brightness']=200
        (folder/'report.json').write_text(json.dumps(result),encoding='utf-8')
        self.assertIn('report parameters or algorithm differ from provenance',verify(folder))
if __name__=='__main__': unittest.main()
