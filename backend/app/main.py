"""Cable-N - public cable sizing website: API + (in production) the built frontend."""
import logging
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .api import assistant, calc, outputs, reference
from .core.config import PROJECT_DIR, get_settings
from .engine.runtime import ENGINE_VERSION

log = logging.getLogger('cablen')
settings = get_settings()

app = FastAPI(title='Cable-N API', version='2.0.0',
              description='Cable-N — Cable Sizing & Engineering Intelligence. Public, stateless calculation API. '
                          f'Calculation engine: {ENGINE_VERSION}. Nothing you send is stored.',
              docs_url='/api/docs', redoc_url=None, openapi_url='/api/openapi.json')

app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=False,
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'],
                   expose_headers=['X-Input-Hash', 'X-Report-Number', 'Content-Disposition'])


@app.middleware('http')
async def guard(request: Request, call_next):
    # request size limit (uploads have their own, larger limit)
    if request.method == 'POST':
        cl = request.headers.get('content-length')
        multipart = request.headers.get('content-type', '').startswith('multipart/')
        limit = (settings.MAX_UPLOAD_MB * 1024 + 64) * 1024 if multipart else settings.MAX_BODY_KB * 1024
        if cl is None and not multipart:
            body = await request.body()
            if len(body) > limit:
                return JSONResponse({'detail': 'Request too large'}, status_code=413)
        elif cl is not None and (not cl.isdigit() or int(cl) > limit):
            return JSONResponse({'detail': 'Request too large'}, status_code=413)
    resp = await call_next(request)
    h = resp.headers
    h.setdefault('X-Content-Type-Options', 'nosniff')
    h.setdefault('X-Frame-Options', 'SAMEORIGIN')
    h.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    h.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if settings.is_production:
        h.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    if request.url.path.startswith('/api/'):
        h.setdefault('Cache-Control', 'no-store')
    return resp


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errs = []
    for e in exc.errors():
        loc = '.'.join(str(x) for x in e['loc'] if x not in ('body',))
        errs.append(f"{loc}: {e['msg']}" if loc else e['msg'])
    return JSONResponse({'detail': {'message': 'Input validation failed', 'errors': errs[:30]}}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception('unhandled error on %s', request.url.path)
    detail = 'Internal server error' if settings.is_production else f'{type(exc).__name__}: {str(exc)[:300]}'
    return JSONResponse({'detail': detail}, status_code=500)


API = '/api/v1'
for r in (calc.router, calc.jobs_router, outputs.router, reference.router, assistant.router):
    app.include_router(r, prefix=API)


@app.on_event('startup')
def _cleanup_stale_temp():
    """Remove report temp folders left by a crash (normally deleted at once)."""
    cutoff = time.time() - 3600
    for d in Path(tempfile.gettempdir()).glob('cablen-rpt-*'):
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


# Production: serve the built website (frontend/dist) from the same origin.
DIST = PROJECT_DIR / 'frontend' / 'dist'


@app.get('/{full_path:path}', include_in_schema=False)
def site(full_path: str):
    if full_path.startswith('api/'):
        raise HTTPException(404)
    if not DIST.exists():
        return JSONResponse({'detail': 'Frontend not built. Run the Vite dev server (http://localhost:5173) or '
                                       '"npm run build" in frontend/.'}, status_code=404)
    root = DIST.resolve()
    target = (DIST / full_path).resolve()
    if root != target and root not in target.parents:
        raise HTTPException(404)
    if target.is_file():
        return FileResponse(target)
    if (target / 'index.html').is_file():          # pre-rendered route (SEO metadata)
        return FileResponse(target / 'index.html')
    return FileResponse(DIST / 'index.html', status_code=200)
