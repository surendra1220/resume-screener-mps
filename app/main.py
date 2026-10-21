import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from .documents import extract, DocumentError, MAX_BYTES
from .engine import analyze, parse_custom_jd
from .models import AnalyzeRequest, Requirement
from .reports import html_report, pdf_report, report_filename

ROOT = Path(__file__).resolve().parents[1]
reports = OrderedDict()
rates = defaultdict(deque)
slots = asyncio.Semaphore(4)
TTL = 3600


@asynccontextmanager
async def lifespan(app):
    async def cleanup():
        while True:
            await asyncio.sleep(60)
            now = time.monotonic()
            for key, (created, _) in list(reports.items()):
                if now - created > TTL:
                    reports.pop(key, None)
            for key, recent in list(rates.items()):
                if not recent or recent[-1] < now - 60:
                    rates.pop(key, None)
    task = asyncio.create_task(cleanup())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    reports.clear()
    rates.clear()


app = FastAPI(title='Proofpoint Resume Screener', version='1.0.0', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware('http')
async def guard(request: Request, call_next):
    # Same-origin mutations; no permissive CORS. Local app has no remote account/authentication surface.
    if request.method == 'POST':
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': 'Cross-origin requests are not allowed.'}, status_code=403)
        key = request.client.host if request.client else 'local'
        now = time.monotonic()
        recent = rates[key]
        while recent and recent[0] < now - 60:
            recent.popleft()
        if len(recent) >= 30:
            return JSONResponse({'detail': 'Too many requests. Try again in a minute.'}, status_code=429)
        recent.append(now)
        # Bound the streamed request body, including chunked uploads.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BYTES + 1024 * 1024:
                return JSONResponse({'detail': 'Request exceeds 11 MB.'}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


@app.exception_handler(DocumentError)
async def document_error(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=422)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'engine': 'local-evidence-rules', 'version': '1.0.0',
            'reference_available': bool(os.environ.get('REFERENCE_REPORT_PATH'))}


@app.get('/api/default-jd')
def default_jd():
    return {'text': (ROOT / 'data/default-jd.md').read_text(), 'label': 'Default · SDET',
            'requirements': json.loads((ROOT / 'data/default-requirements.json').read_text()), 'needs_review': False}


@app.post('/api/extract')
async def upload(file: UploadFile = File(...)):
    async with slots:
        content = await file.read(MAX_BYTES + 1)
        text = await run_in_threadpool(extract, file.filename or '', content)
        await file.close()
        return {'text': text, 'filename': Path(file.filename or 'document').name}


@app.post('/api/parse-jd')
async def jd_upload(file: UploadFile = File(...)):
    result = await upload(file)
    requirements = parse_custom_jd(result['text'])
    if not requirements:
        raise HTTPException(422, 'No requirements extracted. Try a clearer document or enter the JD as text.')
    return {**result, 'label': result['filename'], 'requirements': [r.model_dump() for r in requirements], 'needs_review': True}


@app.post('/api/analyze')
async def screen(body: AnalyzeRequest):
    if len({r.id for r in body.requirements}) != len(body.requirements):
        raise HTTPException(422, 'Requirement IDs must be unique.')
    async with slots:
        report = await run_in_threadpool(analyze, body)
    return cache_report(report)


def cache_report(report):
    now = time.monotonic()
    for key, (created, _) in list(reports.items()):
        if now - created > TTL:
            del reports[key]
    report['download_id'] = uuid.uuid4().hex
    reports[report['download_id']] = (now, report)
    while len(reports) > 50:
        reports.popitem(last=False)
    return report


@app.get('/api/reference-report')
async def reference_report():
    path = os.environ.get('REFERENCE_REPORT_PATH')
    if not path:
        raise HTTPException(404, 'No reference screening is configured.')
    content = await run_in_threadpool(Path(path).read_text)
    return cache_report(json.loads(content))


@app.get('/api/reports/{report_id}/{format}')
async def download(report_id: str, format: str):
    entry = reports.get(report_id)
    if not entry or time.monotonic() - entry[0] > TTL:
        reports.pop(report_id, None)
        raise HTTPException(404, 'Report expired. Run the screening again to regenerate it.')
    report = entry[1]
    if format == 'html':
        data, media = html_report(report), 'text/html; charset=utf-8'
    elif format == 'pdf':
        async with slots:
            data = await run_in_threadpool(pdf_report, report)
        media = 'application/pdf'
    else:
        raise HTTPException(404, 'Choose HTML or PDF.')
    return Response(data, media_type=media, headers={'Content-Disposition': f'attachment; filename="{report_filename(report, format)}"'})


@app.get('/')
def index():
    return HTMLResponse((ROOT / 'app/static/index.html').read_text())


app.mount('/static', StaticFiles(directory=ROOT / 'app/static'), name='static')
