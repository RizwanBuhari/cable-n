"""Reports and exports. The browser sends the INPUTS (never results); the
engine recomputes, the file is built in a temporary directory, streamed back
and deleted. Every document carries the engine version and a SHA-256 of the
validated inputs so it can be traced back to the exact numbers."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..core.protect import rate_limit, run_bounded
from ..engine.runtime import ENGINE_VERSION, latin1
from ..reports import excel
from ..reports.builder import build_report, now_str
from .calc import SLUGS, bad_request, engine_run

router = APIRouter(prefix='/outputs', tags=['reports & exports'])


class Meta(BaseModel):
    title: str = Field('', max_length=160)
    scenario: str = Field('Base case', max_length=120)
    project_name: str = Field('', max_length=160)
    project_number: str = Field('', max_length=60)
    client: str = Field('', max_length=160)
    site: str = Field('', max_length=160)
    prepared_by: str = Field('', max_length=120)
    checked_by: str = Field('', max_length=120)
    revision: str = Field('1', max_length=12)
    report_number: str = Field('', max_length=40)


class OutIn(BaseModel):
    mode: str
    inputs: dict
    meta: Meta = Meta()
    kind: str = Field('detailed', pattern='^(detailed|summary)$')


def input_hash(mode, clean):
    return hashlib.sha256(json.dumps({'mode': mode, 'inputs': clean}, sort_keys=True, default=str)
                          .encode()).hexdigest()


def _mode(m: str) -> str:
    if m in SLUGS:
        return SLUGS[m]
    if m in SLUGS.values():
        return m
    raise HTTPException(422, {'message': 'Unknown calculation mode', 'errors': []})


def _fname(meta: Meta, mode: str, ext: str) -> str:
    base = (meta.report_number or meta.title or mode).strip() or mode
    safe = ''.join(c if c.isalnum() or c in '-_.' else '-' for c in base)[:60].strip('-') or mode
    return f'{safe}.{ext}'


@router.post('/report.pdf')
def report_pdf(body: OutIn, request: Request):
    rate_limit(request, 'report', get_settings().REPORT_RATE_PER_MINUTE)
    mode = _mode(body.mode)
    clean, result = engine_run(mode, body.inputs)
    h = input_hash(mode, clean)
    m = body.meta
    number = m.report_number.strip() or f"CN-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{h[:6].upper()}"
    meta = {'number': latin1(number), 'revision': latin1(m.revision or '1'),
            'title': latin1(m.title or 'Cable calculation'), 'scenario': latin1(m.scenario),
            'project_name': latin1(m.project_name) or None, 'project_number': latin1(m.project_number) or None,
            'client': latin1(m.client) or None, 'site': latin1(m.site) or None,
            'engineer': latin1(m.prepared_by) or None, 'reviewer': latin1(m.checked_by) or None,
            'generated': now_str(), 'engine_version': ENGINE_VERSION, 'input_hash': h, 'status': 'unreviewed',
            'reviews': []}
    try:
        pdf = run_bounded(build_report, meta, mode, clean, result, body.kind, timeout=60)
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        bad_request(e)
    except Exception:  # noqa: BLE001 - details logged by the global handler only
        raise HTTPException(500, 'Report generation failed for these inputs.')
    return Response(pdf, media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{_fname(m, mode, "pdf")}"',
                             'X-Input-Hash': h, 'X-Report-Number': number})


@router.post('/export.xlsx')
def export_xlsx(body: OutIn, request: Request):
    rate_limit(request, 'report', get_settings().REPORT_RATE_PER_MINUTE * 2)
    mode = _mode(body.mode)
    clean, result = engine_run(mode, body.inputs)
    data = excel.export_result(mode, body.meta.title or mode, clean, result)
    return Response(data, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="{_fname(body.meta, mode, "xlsx")}"',
                             'X-Input-Hash': input_hash(mode, clean)})


@router.post('/export.csv')
def export_csv(body: OutIn, request: Request):
    rate_limit(request, 'report', get_settings().REPORT_RATE_PER_MINUTE * 2)
    mode = _mode(body.mode)
    clean, res = engine_run(mode, body.inputs)
    buf = io.StringIO()
    w = csv.writer(buf)
    if mode == 'batch':
        w.writerow(['tag', 'name', 'ib_A', 'runs', 'size_mm2', 'circuit', 'iz_A', 'util_pct', 'vd_pct', 'isc_kA', 'sc',
                    'status', 'governing'])
        for row in res['rows']:
            rec = row.get('rec') or {}
            w.writerow([row['tag'], row.get('name', ''), row['ib'], rec.get('runs'), rec.get('size'),
                        row.get('circuit', ''), rec.get('derated_current'), rec.get('utilisation'),
                        rec.get('voltage_drop'), rec.get('short_circuit'), rec.get('sc_status'), row['status'],
                        row['governing']])
        for row in res['invalid_rows']:
            w.writerow([row['tag'], '', '', '', '', '', '', '', '', '', '', 'invalid', '; '.join(row['errors'])])
    elif mode == 'single_feeder':
        w.writerow(['spacing', 'size_mm2', 'runs', 'iz_A', 'a_per_run', 'util_pct', 'vd_pct', 'isc_kA', 'sc',
                    'recommended'])
        for s in (res.get('single') or {}).get('solutions', []):
            w.writerow(['single', s['size'], 1, s['derated_current'], s['current_per_run'], s['utilisation'],
                        s['voltage_drop'], s['short_circuit'], s['sc_status'], s.get('recommended')])
        for sp, sols in res['detailed_options'].items():
            for s in sols:
                w.writerow([sp, s['size'], s['runs'], s['derated_current'], s['current_per_run'], s['utilisation'],
                            s['voltage_drop'], s['short_circuit'], s['sc_status'], s.get('recommended')])
    elif mode == 'current_rating':
        w.writerow(['position', 'config', 'depth_m', 'base_A', 'Ca', 'Cs', 'Cd', 'Cg', 'Cint', 'rating_A', 'load_A',
                    'util_pct', 'status'])
        for p in res['positions']:
            w.writerow([p['pos'], p['config_label'], p['depth'], p['base'], p['ambient'], p['soil'], p['depth_f'],
                        p['cg'], p['inter'], p['iz'], p.get('load'), p.get('util'), p.get('status')])
    else:
        w.writerow(['position', 'cable', 'x_mm', 'y_mm', 'T1', 'T2', 'T3', 'T4', 'R_ohm_km', 'lambda1', 'lambda2',
                    'Wd_W_m', 'rating_A', 'theta_C', 'load_A'])
        for p in res['placed']:
            w.writerow([p['tag'], p['desig'], p['x'], p['y'], p['T1'], p['T2'], p['T3'], p['T4'], p['R'], p['lam1'],
                        p['lam2'], p['Wd'], p['I'], p['theta_op'], p.get('load')])
    w.writerow([])
    w.writerow(['engine', ENGINE_VERSION])
    w.writerow(['input_sha256', input_hash(mode, clean)])
    w.writerow(['notice', 'Calculation output - requires verification by a qualified electrical engineer.'])
    return Response(buf.getvalue(), media_type='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="{_fname(body.meta, mode, "csv")}"'})
