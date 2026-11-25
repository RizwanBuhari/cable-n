"""Cable-N Assistant (optional, Gemini).

* The key lives only in backend/.env; the browser never sees it.
* Calculation context is sent ONLY when the visitor ticks "share this
  calculation" for that message. The browser sends the INPUTS; the backend
  recomputes them with the engine (it never trusts result numbers from the
  browser) and forwards a compact summary - no project, client or site text.
* Stricter limits than calculations: per-IP per minute, per-IP per day and a
  global daily ceiling, so a public site cannot run up provider costs.
* The assistant is read-only: it cannot run, save, approve or modify
  anything. Any recalculation it suggests is done by the user through the
  deterministic engine.
* With AI disabled / no key / no network the endpoint answers 503 with a
  configuration message and the rest of Cable-N is unaffected.
"""
import json

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.protect import daily_quota, rate_limit
from ..core.config import get_settings

router = APIRouter(prefix='/assistant', tags=['assistant'])

SYSTEM = """You are Cable-N Assistant, a helper inside an electrical cable sizing application used by
engineers on a public engineering website. Rules you must follow:
- You explain; you never calculate new cable ratings, voltage drops, factors or temperatures yourself.
  Every engineering number you mention must come from the CALCULATION CONTEXT provided, quoted as-is.
  If the user asks for a value that is not in the context, say it must be computed with the Cable-N
  engine and tell them which inputs to change and which calculator to use.
- You cannot approve, certify, sign off or declare a design safe or compliant. Remind users that results
  require review by a qualified electrical engineer when they ask about approval or safety.
- Do not invent standards clauses or manufacturer product data.
- Be concise and practical. Use plain text with short lists. Use SI units as shown in the context.
Cable-N features (public website, no accounts; saved work stays in the visitor's browser): Home;
Calculators: (1) Single feeder sizing, (2) Batch cable schedule, (3) Current-rating
verification of duct-bank/buried layouts, (4) Advanced MV/HV IEC 60287/60949 analysis; Cable Library;
Comparison (saved calculations, sensitivity sweeps, cost estimate from user prices); Validation
centre (original benchmark routines); Engineering Resources; Settings. Downloads: PDF, Excel, CSV, JSON."""


class Shared(BaseModel):
    mode: str
    inputs: dict


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=12)
    share: Shared | None = None


def _context(share: Shared) -> str:
    from .calc import SLUGS, engine_run
    mode = SLUGS.get(share.mode, share.mode)
    clean, res = engine_run(mode, share.inputs)
    keep = {'mode': mode, 'engine_version': res.get('engine_version'), 'inputs': clean}
    if mode == 'single_feeder':
        keep.update({k: res.get(k) for k in ('status', 'design_current', 'table_key', 'arrangement_label',
                                             'installation_description', 'checks', 'warnings', 'basis')})
        s = res.get('single') or {}
        keep['single_run'] = {k: s.get(k) for k in ('recommended', 'governing', 'chain', 'exclusions',
                                                    'all_fail_short_circuit')} if s else None
        keep['parallel_best_by_spacing'] = res.get('best_by_spacing')
    elif mode == 'batch':
        keep.update(summary=res.get('summary'), warnings=res.get('warnings'),
                    rows=[{k: x.get(k) for k in ('tag', 'ib', 'status', 'circuit', 'governing', 'exclusions')}
                          for x in res.get('rows', [])][:60], invalid_rows=res.get('invalid_rows'))
    elif mode == 'current_rating':
        keep.update(summary=res.get('summary'), warnings=res.get('warnings'), limitations=res.get('limitations'),
                    positions=[{k: p.get(k) for k in ('pos', 'config_label', 'base', 'ambient', 'soil', 'depth_f',
                                                      'cg', 'inter', 'iz', 'load', 'util', 'status')}
                               for p in res.get('positions', [])])
    else:
        keep.update(governing=res.get('governing'), warnings=res.get('warnings'),
                    placed=[{k: p.get(k) for k in ('tag', 'desig', 'T1', 'T2', 'T3', 'T4', 'R', 'lam1', 'lam2', 'Wd',
                                                   'I', 'theta_op', 'load')} for p in res.get('placed', [])][:40],
                    short_circuit=[{'tag': x['tag'], **(x.get('short_circuit') or {})} for x in res.get('reports', [])][:40])
    txt = json.dumps(keep, default=str)
    return txt[:60000]


@router.get('/status')
def status():
    s = get_settings()
    return {'enabled': s.AI_ENABLED, 'configured': s.ai_configured, 'provider': s.AI_PROVIDER,
            'model': s.GEMINI_MODEL if s.ai_configured else None,
            'message': None if s.ai_configured else
            'The assistant is not enabled on this site. All calculations, reports and tools work without it.',
            'limits': {'per_minute': s.AI_RATE_PER_MINUTE, 'per_day': s.AI_DAILY_PER_IP}}


@router.post('/chat')
def chat(body: ChatIn, request: Request):
    s = get_settings()
    if not s.ai_configured:
        raise HTTPException(503, 'The Cable-N Assistant is not enabled on this site. Calculations, reports and '
                                 'every other feature work without it.')
    rate_limit(request, 'ai', s.AI_RATE_PER_MINUTE)
    contents = []
    for h in body.history[-12:]:
        role = 'model' if h.get('role') == 'assistant' else 'user'
        t = str(h.get('text', ''))[:4000]
        if t:
            contents.append({'role': role, 'parts': [{'text': t}]})
    msg = body.message
    if body.share:
        msg = ('CALCULATION CONTEXT (shared by the user; recomputed by the Cable-N engine):\n'
               + _context(body.share) + '\n\nQUESTION:\n' + msg)
    daily_quota(request, 'ai', s.AI_DAILY_PER_IP, s.AI_DAILY_GLOBAL)
    contents.append({'role': 'user', 'parts': [{'text': msg}]})
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{s.GEMINI_MODEL}:generateContent'
    try:
        resp = httpx.post(url, headers={'x-goog-api-key': s.GEMINI_API_KEY},
                          json={'systemInstruction': {'parts': [{'text': SYSTEM}]}, 'contents': contents,
                                'generationConfig': {'temperature': 0.2, 'maxOutputTokens': 900}},
                          timeout=40)
    except httpx.HTTPError:
        raise HTTPException(503, 'Could not reach the AI provider (network unavailable?). Everything else works.')
    if resp.status_code == 429:
        raise HTTPException(429, 'The AI provider usage limit was reached - try again later.')
    if resp.status_code >= 400:
        raise HTTPException(502, f'AI provider error ({resp.status_code}). Check GEMINI_MODEL / key validity.')
    try:
        cand = resp.json()['candidates'][0]
        answer = ''.join(p.get('text', '') for p in cand['content']['parts']).strip()
    except (KeyError, IndexError, ValueError):
        raise HTTPException(502, 'The AI provider returned no answer (possibly blocked by its safety filter).')
    return {'answer': answer or '(empty answer)', 'shared': bool(body.share),
            'disclaimer': 'AI explanation only - it does not change or approve any calculation.'}
