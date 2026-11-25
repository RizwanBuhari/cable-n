"""Validation centre, cable library, health and the optional ad-free
licence check. All read-only; nothing about visitors is stored."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import re
import threading

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..core.protect import rate_limit
from ..engine.runtime import ENGINE_VERSION, ORIGINAL_SHA256
from ..services import jobs
from ..services.library import records
from ..validation.runner import CASE_BY_ID, CASES, run_case

router = APIRouter(tags=['reference'])

# ---------------------------------------------------------------- health
@router.get('/health')
def health():
    ok = True
    try:
        from ..engine import legacy_engine as L
        ok = bool(L.base_current_tables)
    except Exception:  # noqa: BLE001
        ok = False
    s = get_settings()
    return {'status': 'ok' if ok else 'degraded', 'app': s.APP_NAME, 'engine_ok': ok,
            'engine_version': ENGINE_VERSION, 'original_sha256': ORIGINAL_SHA256[:16],
            'ai_configured': s.ai_configured, 'premium_enabled': bool(s.PREMIUM_SECRET)}


# ---------------------------------------------------------------- validation
_cache: dict[str, dict] = {}   # deterministic: same engine -> same result
_cache_lock = threading.Lock()


def _cached(cid: str) -> dict:
    with _cache_lock:
        if cid in _cache:
            return _cache[cid]
    r = run_case(cid)
    with _cache_lock:
        _cache[cid] = r
    return r


DISCLAIMER = ('Benchmarks are values quoted in the original program (workbook caches and CYMCAP exports). They are '
              'not independently verified by Cable-N. Passing them is not certification, CYMCAP equivalence or IEC '
              'compliance.')


@router.get('/validation/cases')
def cases():
    out = []
    for c in CASES:
        last = _cache.get(c['id'])
        out.append({'id': c['id'], 'title': c['title'], 'function': c['fn'] + '()', 'source': c['source'],
                    'benchmark_kind': c['kind'], 'note': c['note'], 'tolerance_pct': c.get('tol_pct'),
                    'tolerance_K': c.get('tol_K'), 'tolerance_source': c.get('tol_source'),
                    'last_status': last['status'] if last else None})
    return {'cases': out, 'engine_version': ENGINE_VERSION, 'original_sha256': ORIGINAL_SHA256,
            'disclaimer': DISCLAIMER}


class RunIn(BaseModel):
    case_ids: list[str] = []


def _job(progress, cancelled, ids):
    results = []
    for i, cid in enumerate(ids):
        if cancelled():
            break
        results.append(_cached(cid))
        progress(i + 1, len(ids))
    return {'results': results}


@router.post('/validation/run')
def run(body: RunIn, request: Request):
    rate_limit(request, 'validation', get_settings().VALIDATION_RATE_PER_MINUTE)
    ids = body.case_ids or [c['id'] for c in CASES]
    for i in ids:
        if i not in CASE_BY_ID:
            raise HTTPException(404, f'Unknown case {i}')
    return {'job_id': jobs.submit('validation', _job, ids), 'total': len(ids)}


@router.get('/validation/cases/{cid}')
def case_detail(cid: str, request: Request):
    if cid not in CASE_BY_ID:
        raise HTTPException(404, 'Unknown case')
    if cid not in _cache:
        rate_limit(request, 'validation', get_settings().VALIDATION_RATE_PER_MINUTE)
    return _cached(cid)


@router.get('/validation/report.json')
def validation_export(request: Request):
    rate_limit(request, 'validation', get_settings().VALIDATION_RATE_PER_MINUTE)
    payload = {'engine_version': ENGINE_VERSION, 'original_sha256': ORIGINAL_SHA256,
               'cases': {c['id']: _cached(c['id']) for c in CASES}, 'disclaimer': DISCLAIMER}
    return Response(json.dumps(payload, indent=2, default=str), media_type='application/json',
                    headers={'Content-Disposition': 'attachment; filename="cable-n-validation.json"'})


# ---------------------------------------------------------------- cable library
@router.get('/cable-library')
def library():
    """Built-in generic engine-table data and illustrative Mode 4 presets.
    Custom cables are kept in the visitor's browser, not on the server."""
    return {'records': list(records()),
            'notice': 'Generic table data from the calculation program - not any manufacturer\'s product data. '
                      'Presets are illustrative starting points; replace with datasheet values.'}


PATTERNS = [
    ('size_mm2', r'(\d{2,4})\s*(?:mm2|mm²|sq\.?\s*mm)', float),
    ('voltage_kv', r'(\d{1,3}(?:\.\d+)?)\s*/\s*(\d{1,3}(?:\.\d+)?)\s*(?:\(\d+(?:\.\d+)?\))?\s*kV', None),
    ('dc', r'(?:conductor\s+diameter|diameter\s+of\s+conductor)[^\d]{0,40}(\d{1,2}(?:\.\d+)?)', float),
    ('ti', r'(?:insulation\s+thickness|thickness\s+of\s+insulation)[^\d]{0,40}(\d{1,2}(?:\.\d+)?)', float),
    ('De', r'(?:overall|outer)\s+diameter[^\d]{0,40}(\d{2,3}(?:\.\d+)?)', float),
    ('tj', r'(?:sheath|jacket)\s+thickness[^\d]{0,40}(\d{1,2}(?:\.\d+)?)', float),
    ('R20_dc', r'(?:d\.?c\.?\s+resistance|max(?:imum)?\.?\s+(?:d\.?c\.?\s+)?resistance)[^\d]{0,60}(\d+\.\d+)', float),
    ('rating_A', r'(?:current\s+rating|ampacity|continuous\s+current)[^\d]{0,60}(\d{2,4})\s*A', float),
]


@router.post('/cable-library/extract-datasheet')
async def extract_datasheet(request: Request, file: UploadFile = File(...)):
    """Conventional (non-AI) PDF text extraction. Candidates carry their page
    and surrounding text and MUST be verified by the user. The file is read in
    memory and discarded; nothing is stored."""
    rate_limit(request, 'report', get_settings().REPORT_RATE_PER_MINUTE)
    if not (file.filename or '').lower().endswith('.pdf'):
        raise HTTPException(400, 'Upload a PDF datasheet')
    limit = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f'PDF larger than {get_settings().MAX_UPLOAD_MB} MB')
    if not data.startswith(b'%PDF'):
        raise HTTPException(400, 'Not a PDF file')
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(i + 1, (p.extract_text() or '')) for i, p in enumerate(reader.pages[:30])]
    except Exception:  # noqa: BLE001
        raise HTTPException(400, 'Could not read text from this PDF (it may be scanned or encrypted).')
    cands = []
    for pg, text in pages:
        flat = re.sub(r'\s+', ' ', text)
        for field, pat, conv in PATTERNS:
            n = 0
            for m in re.finditer(pat, flat, re.I):
                try:
                    val = float(m.group(2)) if field == 'voltage_kv' else conv(m.group(1))
                except ValueError:
                    continue
                s, e = max(0, m.start() - 60), min(len(flat), m.end() + 60)
                cands.append({'field': field, 'value': val, 'page': pg, 'context': flat[s:e]})
                n += 1
                if n >= 6:
                    break
    words = ' '.join(t for _, t in pages).lower()
    hints = {'material': 'AL' if 'alumin' in words and 'copper' not in words else ('CU' if 'copper' in words else None),
             'insulation': 'XLPE' if 'xlpe' in words else ('EPR' if 'epr' in words else ('PVC' if 'pvc' in words else None)),
             'armour': next((a for a in ('AWA', 'SWA', 'STA', 'ATA') if a.lower() in words), None)}
    return {'filename': file.filename, 'pages': len(pages), 'candidates': cands[:120], 'hints': hints,
            'text_found': any(t.strip() for _, t in pages),
            'notice': 'Extracted values are UNVERIFIED candidates. Check each against the page shown before using '
                      'them. Saved custom cables stay in your browser only.'}


# ---------------------------------------------------------------- optional ad-free licence keys
def sign_key(payload: dict, secret: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f'CN1.{body}.{sig}'


class KeyIn(BaseModel):
    key: str = Field(min_length=10, max_length=600)


@router.post('/premium/verify')
def verify_key(body: KeyIn, request: Request):
    """Offline-verifiable ad-free licence (HMAC-signed, no accounts). Off unless
    PREMIUM_SECRET is set. A payment provider can later issue these keys."""
    rate_limit(request, 'premium', 10)
    secret = get_settings().PREMIUM_SECRET
    if not secret:
        raise HTTPException(404, 'Ad-free licences are not enabled on this site.')
    try:
        tag, body64, sig = body.key.strip().split('.')
        assert tag == 'CN1'
        good = hmac.new(secret.encode(), body64.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(good, sig):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body64 + '=' * (-len(body64) % 4)))
    except Exception:  # noqa: BLE001
        raise HTTPException(400, 'This licence key is not valid.')
    from datetime import date
    exp = payload.get('exp')
    if exp and date.fromisoformat(exp) < date.today():
        raise HTTPException(400, f'This licence key expired on {exp}.')
    return {'valid': True, 'ad_free': True, 'expires': exp, 'label': payload.get('label', '')}
