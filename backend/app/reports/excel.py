"""Excel import/export with openpyxl."""
from __future__ import annotations

import io

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HEAD_FILL = PatternFill('solid', fgColor='CE1B28')
HEAD_FONT = Font(bold=True, color='FFFFFF')
FEEDER_COLUMNS = [
    ('tag', 'Feeder tag', 'F-01'), ('name', 'Feeder name', 'Pump P-101'),
    ('load_mode', 'Load mode (current/power)', 'current'), ('current', 'Load current (A)', 120),
    ('power', 'Power value', None), ('power_unit', 'Power unit (KW/KVA/MW/MVA)', None),
    ('cable_length', 'Route length (m)', 150), ('power_factor', 'Power factor override (blank = common)', None),
    ('voltage_drop_limit_pct', 'VD limit % override (blank = common)', None),
]


def _sheet(ws, heads, rows, widths=None):
    ws.append(heads)
    for c in ws[1]:
        c.fill = HEAD_FILL; c.font = HEAD_FONT; c.alignment = Alignment(horizontal='center', wrap_text=True)
    for r in rows:
        ws.append(r)
    for i, h in enumerate(heads, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = (widths or {}).get(i, max(12, len(str(h)) + 2))
    ws.freeze_panes = 'A2'


def feeder_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = 'Feeders'
    _sheet(ws, [c[1] for c in FEEDER_COLUMNS], [[c[2] for c in FEEDER_COLUMNS]])
    dv = DataValidation(type='list', formula1='"current,power"', allow_blank=False)
    ws.add_data_validation(dv); dv.add('C2:C501')
    du = DataValidation(type='list', formula1='"KW,KVA,MW,MVA"', allow_blank=True)
    ws.add_data_validation(du); du.add('F2:F501')
    info = wb.create_sheet('Instructions')
    for line in ['Cable-N batch feeder template.',
                 'One row per feeder. Row 2 is an example - overwrite or delete it.',
                 'Load mode "current": fill Load current. Load mode "power": fill Power value and unit.',
                 'Power factor / VD limit overrides are optional; blank uses the common project values.',
                 'Common parameters (voltage, phase, construction, installation, fault level) are set in the app.',
                 'Rows with errors are reported individually and never block valid rows.']:
        info.append([line])
    info.column_dimensions['A'].width = 110
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def _num(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v  # left as text -> row-level validation reports it


def parse_feeders(data: bytes) -> tuple[list[dict], list[str]]:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb['Feeders'] if 'Feeders' in wb.sheetnames else wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], ['The sheet is empty.']
    labels = {c[1].lower(): c[0] for c in FEEDER_COLUMNS}
    keys = {c[0] for c in FEEDER_COLUMNS}
    header = []
    for h in rows[0]:
        h = str(h or '').strip()
        header.append(labels.get(h.lower(), h if h in keys else None))
    problems = []
    if 'cable_length' not in header:
        problems.append('Missing column "Route length (m)". Use the downloadable template.')
        return [], problems
    out = []
    for i, r in enumerate(rows[1:], start=2):
        if not any(v not in (None, '') for v in r):
            continue
        d = {}
        for k, v in zip(header, r):
            if not k:
                continue
            d[k] = _num(v) if k in ('current', 'power', 'cable_length', 'power_factor',
                                     'voltage_drop_limit_pct') else (str(v).strip() if v is not None else None)
        d['load_mode'] = (d.get('load_mode') or 'current').lower()
        if d['load_mode'] not in ('current', 'power'):
            problems.append(f'Row {i}: load mode must be "current" or "power".')
            d['load_mode'] = 'current'
        for k in ('current', 'power', 'cable_length', 'power_factor', 'voltage_drop_limit_pct'):
            if isinstance(d.get(k), str):
                problems.append(f'Row {i}: "{d[k]}" in {k} is not a number.')
                d[k] = None
        if d.get('power_unit'):
            d['power_unit'] = d['power_unit'].upper()
        out.append(d)
    if len(out) > 500:
        problems.append('Only the first 500 feeders are imported.')
        out = out[:500]
    return out, problems


def export_result(mode: str, title: str, inputs: dict, result: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    if mode == 'batch':
        ws.title = 'Cable Schedule'
        rows = []
        for r in result['rows']:
            rec = r.get('rec') or {}
            rows.append([r['tag'], r.get('name', ''), round(r['ib'], 2), rec.get('runs'), rec.get('size'),
                         r.get('circuit', ''), rec.get('spacing'), round(rec['derated_current'], 1) if rec else None,
                         round(rec['utilisation'], 1) if rec else None, round(rec['voltage_drop'], 3) if rec else None,
                         round(rec['short_circuit'], 2) if rec else None, rec.get('sc_status') or '-',
                         r['status'], r['governing'],
                         ('Parallel-run fallback. ' if r['multi_fallback'] else '') + (r.get('exclusions') or '')])
        for r in result['invalid_rows']:
            rows.append([r['tag'], '', None, None, None, '', None, None, None, None, None, '-', 'invalid',
                         '', '; '.join(r['errors'])])
        _sheet(ws, ['Tag', 'Name', 'Ib (A)', 'Runs', 'Size (mm2)', 'Circuit', 'Spacing', 'Iz (A)', 'Util %',
                    'VD %', 'Isc (kA)', 'SC', 'Status', 'Governing constraint', 'Remarks'], rows,
               {6: 40, 14: 28, 15: 50})
    elif mode == 'single_feeder':
        ws.title = 'Single-run options'
        _sheet(ws, ['Size (mm2)', 'Iz (A)', 'Util %', 'VD %', 'Isc (kA)', 'Req (kA)', 'SC', 'Recommended'],
               [[s['size'], round(s['derated_current'], 1), round(s['utilisation'], 1), round(s['voltage_drop'], 3),
                 round(s['short_circuit'], 2), s.get('sc_required'), s['sc_status'] or '-',
                 'yes' if s.get('recommended') else ''] for s in (result['single'] or {}).get('solutions', [])])
        ws2 = wb.create_sheet('Parallel options')
        rows = []
        for sp, sols in result['detailed_options'].items():
            for s in sols:
                rows.append([sp, s['size'], s['runs'], round(s['derated_current'], 1), round(s['current_per_run'], 1),
                             round(s['utilisation'], 1), round(s['voltage_drop'], 3), round(s['short_circuit'], 2),
                             s['sc_status'] or '-', 'yes' if s.get('recommended') else ''])
        _sheet(ws2, ['Spacing', 'Size (mm2)', 'Runs', 'Iz (A)', 'A/run', 'Util %', 'VD %', 'Isc (kA)', 'SC',
                     'Recommended'], rows)
    elif mode == 'current_rating':
        ws.title = 'Ratings'
        _sheet(ws, ['Position', 'Config', 'Depth m', 'Ibase A', 'Ca', 'Cs', 'Cd', 'Cg', 'Cint', 'Rating A',
                    'Load A', 'Util %', 'Status'],
               [[p['pos'], p['config_label'], round(p['depth'], 3), p['base'], round(p['ambient'], 4), p['soil'],
                 p['depth_f'], p['cg'], p['inter'], round(p['iz'], 1), p.get('load'),
                 round(p['util'], 1) if p.get('util') is not None else None, p.get('status') or '-']
                for p in result['positions']])
    elif mode == 'advanced_mvhv':
        ws.title = 'Ratings'
        _sheet(ws, ['Position', 'Cable', 'x mm', 'y mm', 'T1', 'T2', 'T3', 'T4', 'R ac ohm/km', 'lambda1',
                    'lambda2', 'Wd W/m', 'dT int K', 'Rating A', 'Tcond C', 'Load A'],
               [[p['tag'], p['desig'], p['x'], p['y'], p['T1'], p['T2'], p['T3'], p['T4'], p['R'], p['lam1'],
                 p['lam2'], p['Wd'], p['dt_int'], p['I'], p['theta_op'], p.get('load')] for p in result['placed']])
        ws2 = wb.create_sheet('Electrical')
        _sheet(ws2, ['Position', 'I A', 'C uF/km', 'Ich A/km', 'XL ohm/km', 'R ohm/km', 'Wd W/m', 'Z1 R', 'Z1 X',
                     'Z0 R', 'Z0 X', 'V sheath trefoil V', 'Icond kA', 'Metallic withstand kA', 'SC adequate'],
               [[r['tag'], r['I'], r['electrical']['C'], r['electrical']['Ich'], r['electrical']['XL'],
                 r['electrical']['R'], r['electrical']['Wd'], r['sequence']['Z1']['re'], r['sequence']['Z1']['im'],
                 r['sequence']['Z0']['re'], r['sequence']['Z0']['im'], r['induced']['V_tref'],
                 r['short_circuit']['Icond'], r['short_circuit']['total'],
                 'yes' if r['short_circuit']['adequate'] else 'REVIEW'] for r in result['reports']])
    meta = wb.create_sheet('Info')
    for row in [['Title', title], ['Mode', mode], ['Engine', result.get('engine_version')],
                ['Notice', 'Calculation output - requires review by a qualified electrical engineer.']]:
        meta.append(row)
    for w in result.get('warnings') or []:
        meta.append(['Warning', w])
    meta.column_dimensions['B'].width = 120
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()
