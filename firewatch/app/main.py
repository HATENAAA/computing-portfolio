from pathlib import Path
import io, json, os, shutil, sqlite3, uuid, warnings, hashlib, platform
from datetime import datetime, timezone
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from .detector import analyze, Config

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('FIREWATCH_DATA', ROOT.parent / 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'history.sqlite3'
with sqlite3.connect(DB) as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT, filename TEXT, result TEXT)')
app = FastAPI(title='FireWatch 火焰图像分析', version='1.0.0')
app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 12_000_000

def decode(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP'): raise ValueError('仅支持 JPEG、PNG、WebP')
                if image.width * image.height > MAX_PIXELS: raise ValueError('图片不能超过 1200 万像素')
                image.load()
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if img is None: raise ValueError('无法解码图片')
        return img
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('无效图片或图片尺寸过大') from exc

def fetch(run_id):
    with sqlite3.connect(DB) as conn:
        row = conn.execute('SELECT result FROM runs WHERE id=?', (run_id,)).fetchone()
    if row is None: raise HTTPException(404, '记录不存在')
    return json.loads(row[0])

def persist(raw, filename, cfg):
    img = decode(raw)
    result, assets = analyze(img, cfg)
    run_id = uuid.uuid4().hex
    folder = DATA/run_id
    folder.mkdir()
    try:
        output_hashes = {}
        for name, image in assets.items():
            ok, encoded = cv2.imencode('.png', image)
            if not ok: raise RuntimeError('图片编码失败')
            payload = encoded.tobytes()
            (folder/f'{name}.png').write_bytes(payload)
            output_hashes[name + '.png'] = hashlib.sha256(payload).hexdigest()
        source_hash = hashlib.sha256(raw).hexdigest()
        code_hash = hashlib.sha256((ROOT/'detector.py').read_bytes()).hexdigest()
        signature = {'source_sha256': source_hash, 'detector_sha256': code_hash,
                     'algorithm': result['algorithm'], 'config': result['config'],
                     'opencv': cv2.__version__, 'numpy': np.__version__}
        fingerprint = hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        result['provenance'] = dict(signature, fingerprint=fingerprint, source_bytes=len(raw),
                                    python=platform.python_version(), output_sha256=output_hashes)
        result.update(id=run_id, filename=filename.replace('\\','/').split('/')[-1][:180],
                      created=datetime.now(timezone.utc).isoformat(),
                      assets={name: f'/api/runs/{run_id}/images/{name}' for name in assets})
        (folder/'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        with sqlite3.connect(DB) as conn:
            conn.execute('INSERT INTO runs VALUES (?,?,?,?)', (run_id,result['created'],result['filename'],json.dumps(result,ensure_ascii=False)))
        return result
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise

@app.get('/')
def home(): return FileResponse(ROOT/'static/index.html')
@app.get('/api/health')
def health(): return {'status':'ok','algorithm':'color-edge-v2'}
@app.post('/api/analyze')
async def detect(file: UploadFile = File(...), brightness: int = Form(150, ge=0, le=255),
                 edge_ratio: float = Form(0.6, ge=0, le=1), min_area_ratio: float = Form(0.002, ge=0, le=1),
                 min_component: int = Form(40, ge=1, le=100000)):
    try:
        raw = await file.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES: raise HTTPException(413, '文件不能超过 10 MB')
        try: return await run_in_threadpool(persist, raw, file.filename or 'image', Config(brightness,edge_ratio,min_area_ratio,min_component))
        except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    finally: await file.close()
@app.get('/api/runs')
def history(limit: int = Query(20, ge=1, le=100)):
    with sqlite3.connect(DB) as conn:
        rows=conn.execute('SELECT result FROM runs ORDER BY created DESC LIMIT ?', (limit,)).fetchall()
    return [json.loads(r[0]) for r in rows]
@app.get('/api/runs/{run_id}')
def get_run(run_id: str): return fetch(run_id)
@app.get('/api/runs/{run_id}/report')
def report(run_id: str):
    return Response(json.dumps(fetch(run_id),ensure_ascii=False,indent=2),media_type='application/json',
                    headers={'Content-Disposition':f'attachment; filename="firewatch-{run_id}.json"'})
@app.get('/api/runs/{run_id}/images/{name}')
def image(run_id: str, name: str):
    result=fetch(run_id)
    if name not in result['assets']: raise HTTPException(404,'图片不存在')
    return FileResponse(DATA/run_id/f'{name}.png')
