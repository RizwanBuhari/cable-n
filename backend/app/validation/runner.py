"""Runs the ORIGINAL validation routines unchanged and structures their output.

The routines only print. Each one runs with stdout captured; the raw printout
is kept verbatim and a DEDICATED parser per routine (written against its
exact print format) extracts comparison rows. A generic regex was tried first
and mis-paired numbers (e.g. compared a lead-sheath withstand with its
pre-factor value), so every parser below is format-specific and covered by
tests/test_validation_parsers.py.

Each row is classed:
  headline      - what the routine presents as its result (ratings,
                  conductor temperatures, final withstand values)
  intermediate  - component quantities it also prints (T1..T4, lambda, R ...)
Case status is judged on headline rows; intermediate rows are judged and
shown separately so a gap in a component is never hidden.

Statuses:
  PASS               every headline row is within tolerance
  OUTSIDE_TOLERANCE  at least one headline row exceeds it (reported, never hidden)
  KNOWN_GAPS         the routine itself flags quantities as open gaps
  INFO               nothing comparable could be extracted
  ERROR              the routine raised

Tolerances: where a routine states one (mode4_validate 0.5 %, emergency
"about 5 %") it is used. Otherwise Cable-N applies a documented acceptance
tolerance of 5 % on ratings and 5 K on conductor temperature - a common
inter-tool comparison band for IEC 60287 studies, NOT a compliance limit.

Benchmarks are values written into the source program (workbook caches and
CYMCAP exports quoted by the original author). They are NOT independently
verified by Cable-N, and passing them is not certification.
"""
from __future__ import annotations

import math
import re
import time
import traceback

from ..engine import legacy_engine as L
from ..engine.runtime import ENGINE_VERSION, run_engine

N = r'[+-]?\d+(?:\.\d+)?'

CASES = [
    dict(id='mode4_validate', fn='mode4_validate', title='IEC 60287 rating chain vs reference workbook',
         source='Reference workbook cached ratings (HV_Current_rating_calculation_version_8)',
         kind='workbook', tol_pct=0.5, tol_source='routine docstring ("all six targets within 0.5%")',
         note='Buried 1/2/3 circuits, duct, duct+bank and air trefoil for the 1x400 132 kV reference cable. '
              'The duct+bank row compares the engine with a target the original author updated from the '
              'engine itself (see cymcap_ductbank_validate).'),
    dict(id='suite_validate', fn='suite_validate', title='Adiabatic / electrical / sequence / induced suite',
         source='Reference workbook cached values', kind='workbook', tol_pct=1.0,
         tol_source='Cable-N acceptance (1 %) - routine states none',
         note='Short-circuit withstand, capacitance, charging current, reactance, Z0 and induced voltage.'),
    dict(id='emergency_validate', fn='emergency_validate', title='IEC 60853-2 emergency transient',
         source='Reference workbook emergency sheet', kind='workbook', tol_pct=5.0,
         tol_source='original program comment ("agreement to about 5 %")',
         note='Temperature-rise curve theta(t); QA/QB/a/b/Ta/Tb are intermediate constants.'),
    dict(id='mode4_cymcap_validate', fn='mode4_cymcap_validate', answers=['demo'],
         title='Buried trefoil mutual-heating cross-check', source='Reference workbook', kind='workbook',
         tol_pct=0.5, tol_source='same targets as mode4_validate (0.5 %)', note='1, 2 and 3 buried trefoil circuits.'),
    dict(id='cymcap_ductbank_validate', fn='cymcap_ductbank_validate',
         title='CYMCAP duct bank 1x630 33 kV (Option 1)', source='CYMCAP 9.1 report quoted in the source program',
         kind='cymcap', tol_pct=5.0, tol_source='Cable-N acceptance (5 % on rating)',
         note='Governing duct vs CYMCAP common ampacity 242.78 A.'),
    dict(id='cymcap_3core_validate', fn='cymcap_3core_validate',
         title='Screened 3-core 3x240 33 kV (legacy check)', source='CYMCAP 8.1 TRANSCO report quoted in source',
         kind='cymcap', tol_pct=None, tol_source="routine's own OK/GAP flags",
         note='Legacy check kept in the original; it flags T2/T4/lambda as OPEN GAPS itself. The later '
              'transco_validate case re-checks the same cable with the calibrated chain.'),
    dict(id='volta_validate', fn='volta_validate', title='Multi-bank mixed-load (VOLTA H3-H3)',
         source='CYMCAP 8.1 export quoted in source', kind='cymcap', tol_K=5.0,
         tol_source='Cable-N acceptance (5 K on conductor temperature)',
         note='Three soil models: A Neher single rectangle, B CYMCAP effective rho, C layer stack. '
              'All rows are conductor temperatures and are all judged.'),
    dict(id='transco_validate', fn='transco_validate', title='Screened 3-core TRANSCO 3x240 duct',
         source='CYMCAP 8.1 export quoted in source', kind='cymcap', tol_pct=5.0,
         tol_source='Cable-N acceptance (5 % on rating)',
         note='Ampacity under progressively CYMCAP-matched settings vs 310.1 A; per-quantity table is intermediate.'),
    dict(id='soil_validate', fn='soil_validate', title='Effective soil resistivity (100 cables)',
         source='CYMCAP 8.1 rho_Ts values quoted in source', kind='cymcap', tol_pct=25.0,
         tol_source='routine summary (blend model worst case 25 %)',
         note='Headline = the default "blend" model per section; Neher and radial columns are intermediate.'),
    dict(id='ground3c_validate', fn='ground3c_validate', title='Direct-buried 3-core TAQA 3x400 11 kV',
         source='CYMCAP 9.0 export quoted in source', kind='cymcap', tol_pct=5.0, tol_K=5.0,
         tol_source='Cable-N acceptance (5 % rating, 5 K temperature)',
         note='Capacitance is documented ~10 % low in the source (no effect on rating at 11 kV).'),
    dict(id='ductbank_validate', fn='ductbank_validate', title='Buried duct bank TRANSCO 1x630 (2 and 4 circuits)',
         source='CYMCAP 9.0 exports quoted in source', kind='cymcap', tol_pct=5.0,
         tol_source='Cable-N acceptance (5 % on rating)', note='Three soil-rho routes per circuit count.'),
    dict(id='esf_validate', fn='esf_validate', title='Air / trough TAQA ESF 1x630 + 3x300',
         source='CYMCAP 8.1 exports quoted in source', kind='cymcap', tol_pct=5.0,
         tol_source='Cable-N acceptance (5 % on rating)', note='Per-quantity table is intermediate.'),
]
CASE_BY_ID = {c['id']: c for c in CASES}


def _row(label, computed, reference, unit='%', kind='headline', deviation=None, **kw):
    if deviation is None and computed is not None and reference not in (None, 0):
        deviation = (computed - reference) / reference * 100 if unit == '%' else computed - reference
    r = {'label': label.strip(), 'computed': computed, 'reference': reference, 'deviation': deviation,
         'unit': unit, 'kind': kind}
    r.update(kw)
    return r


def _f(s):
    return float(s)


# ------------------------------------------------------------ parsers
def p_mode4(text):
    rows = []
    for m in re.finditer(rf'^\s*(.+?):\s+({N}) A\s+\(workbook ({N}) A, dev ({N})%\)', text, re.M):
        rows.append(_row(m.group(1), _f(m.group(2)), _f(m.group(3)), deviation=_f(m.group(4))))
    return rows


def p_suite(text):
    rows = []
    for line in text.splitlines():
        s = line.strip()
        m = re.match(rf'^(conductor|Cu screen adiabatic):\s+({N}) kA \(workbook ({N})\)', s)
        if m:
            rows.append(_row(m.group(1) + ' withstand (kA)', _f(m.group(2)), _f(m.group(3))))
            continue
        m = re.match(rf'^lead:.*=\s*({N}) kA \(workbook .*=\s*({N})\)', s)
        if m:
            rows.append(_row('lead sheath withstand incl. e1 (kA)', _f(m.group(1)), _f(m.group(2))))
            continue
        for name, unit in (('C', 'uF/km'), ('Ich', 'A/km'), ('XL', 'ohm/km')):
            m = re.search(rf'(?:^|\| ){name} ({N}) {re.escape(unit)} \(({N})\)', s)
            if m:
                rows.append(_row(f'{name} ({unit})', _f(m.group(1)), _f(m.group(2))))
        m = re.search(rf'X1 ({N}) \(({N})\)', s)
        if m:
            rows.append(_row('X1 (ohm/km)', _f(m.group(1)), _f(m.group(2))))
        m = re.search(rf'\|Z0\| ({N}) \(({N})\)', s)
        if m:
            rows.append(_row('|Z0| (ohm/km)', _f(m.group(1)), _f(m.group(2))))
        m = re.match(rf'^({N}) V/m \(workbook ({N})\)', s)
        if m:
            rows.append(_row('induced voltage (V/m)', _f(m.group(1)), _f(m.group(2))))
    return rows


def p_emergency(text):
    rows = []
    for name, got, ref in re.findall(rf'(\w+)=({N}) \(wb ({N})\)', text):
        rows.append(_row(name, _f(got), _f(ref), kind='intermediate'))
    for t, got, ref, dev in re.findall(rf't=({N})h: theta=({N})\s+wb=({N})\s+dev=({N})%', text):
        rows.append(_row(f'theta rise at {t} h (K)', _f(got), _f(ref), deviation=_f(dev)))
    return rows


def p_m4cymcap(text):
    return [_row(f'{n} circuit(s) rating (A)', _f(a), _f(b), deviation=_f(d))
            for n, a, b, d in re.findall(rf'(\d) circuit\(s\): engine ({N}) A\s+\|\s+reference ({N}) A\s+\|\s+dev ({N})%', text)]


def p_cymcap_duct(text):
    rows = []
    ref = re.search(rf'CYMCAP ampacity \(all cables\): ({N}) A', text)
    gov = re.search(rf'Governing \(hottest\) duct:\s+({N}) A\s+-> dev ({N})%', text)
    if ref and gov:
        rows.append(_row('governing duct rating (A)', _f(gov.group(1)), _f(ref.group(1)), deviation=_f(gov.group(2))))
    m = re.search(rf'lambda2 \(.*\):\s+({N})\s+\(CYMCAP ({N})\)', text)
    if m:
        rows.append(_row('lambda2', _f(m.group(1)), _f(m.group(2)), kind='intermediate'))
    m = re.search(rf'Effective soil rho \(Neher\):\s+({N})\s+\(CYMCAP ({N})\)', text)
    if m:
        rows.append(_row('effective soil rho (K.m/W)', _f(m.group(1)), _f(m.group(2)), kind='intermediate'))
    return rows


def p_3core(text):
    rows = []
    for q, a, b, d, flag in re.findall(rf'^(\w+)\s+({N})\s+({N})\s+({N})\s+(OK|GAP)\s*$', text, re.M):
        a, b = _f(a), _f(b)
        rows.append(_row(q, a, b, kind='intermediate', flag=flag, routine_dev_abs=_f(d)))
    return rows


def p_volta(text):
    rows = []
    block = ''
    for line in text.splitlines():
        m = re.match(r'^([ABC])\) (.*)$', line.strip())
        if m:
            block = f'{m.group(1)} ({m.group(2)})'
            continue
        m = re.match(rf'^(B\d+R\d+@\d+)\s+(\S+)\s+({N})\s+{N}\s+{N}\s+{N}\s+({N})\s+({N})\s+({N})\s*$', line.strip())
        if m:
            rows.append(_row(f'{block[:1]} {m.group(1)} {m.group(2)} @ {m.group(3)} A', _f(m.group(4)), _f(m.group(5)),
                             unit='K', deviation=_f(m.group(6)), group=block))
    return rows


def p_transco(text):
    rows = []
    for q, a, b, d in re.findall(rf'^(T1|T2|T3|ys|yp|R|lam1|lam2)\s+({N})\s+({N})\s+({N})\s*$', text, re.M):
        rows.append(_row(q, _f(a), _f(b), kind='intermediate', deviation=_f(d)))
    ref = re.search(rf'Ampacity \(CYMCAP ({N}) A\)', text)
    for lbl, i, d in re.findall(rf'^(.+?)\s+rho\s+{N}\s+T4\s+{N}\s+I\s+({N}) A\s+dev\s+({N})%', text, re.M):
        rows.append(_row(lbl + ' - rating (A)', _f(i), _f(ref.group(1)) if ref else None, deviation=_f(d)))
    return rows


def p_soil(text):
    rows = []
    for name, n, ne, ra, bl in re.findall(rf'^(.+?)\s+(\d+)\s+{N}-\s*{N}\s+({N})\s+({N})\s+({N})\s*$', text, re.M):
        rows.append(_row(f'{name.strip()} ({n} cables) - blend', None, None, deviation=_f(bl)))
        rows.append(_row(f'{name.strip()} - Neher', None, None, deviation=_f(ne), kind='intermediate'))
        rows.append(_row(f'{name.strip()} - radial', None, None, deviation=_f(ra), kind='intermediate'))
    return rows


def p_ground3c(text):
    rows = []
    for q, a, b in re.findall(rf'^(T1|T2|T3|ys|yp|R|lam1|lam2|Wd)\s+({N})\s+({N})\s*$', text, re.M):
        a, b = _f(a), _f(b)
        rows.append(_row(q + ' (CYMCAP printed to 2 dp)', a, b, kind='intermediate',
                         deviation=round(a, 2) - b, unit='abs (2 dp)', within_override=round(a, 2) == round(b, 2)))
    m = re.search(rf'ours ({N}) A vs CYMCAP ({N}) A -> ({N}) pct', text)
    if m:
        rows.append(_row('equally-loaded ampacity (A)', _f(m.group(1)), _f(m.group(2)), deviation=_f(m.group(3))))
    for pos, t4, t4c, dti, dtic, tc, tcc in re.findall(
            rf'^(C\d)\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})\s*$', text, re.M):
        rows.append(_row(f'{pos} conductor temperature (C)', _f(tc), _f(tcc), unit='K'))
        rows.append(_row(f'{pos} dTheta_int (K)', _f(dti), _f(dtic), unit='K', kind='intermediate'))
    for q, a, b, d in re.findall(rf'^(C \(uF/km\)|Ich \(A/km\)|XL \(ohm/km\)|Z1 R \(ohm/km\)|Z1 X \(ohm/km\))\s+({N})\s+({N})\s+({N})\s*$', text, re.M):
        rows.append(_row(q, _f(a), _f(b), kind='intermediate', deviation=_f(d)))
    return rows


def p_ductbank(text):
    rows = []
    ref = None
    head = ''
    for line in text.splitlines():
        s = line.strip()
        m = re.match(rf'^(\d) circuits .*CYMCAP ({N}) A', s)
        if m:
            head, ref = f'{m.group(1)} circuits', _f(m.group(2))
            continue
        m = re.match(rf'^(.+?)\s+rho {N} \(CYM {N}\)\s+I\s+({N}) A\s+dev\s+({N}) pct', s)
        if m and ref:
            rows.append(_row(f'{head} - {m.group(1)} rating (A)', _f(m.group(2)), ref, deviation=_f(m.group(3))))
            continue
        m = re.match(rf'^T4 .*?({N}) vs ({N})\s+dev ({N}) pct', s)
        if m:
            rows.append(_row(f'{head} - T4', _f(m.group(1)), _f(m.group(2)), deviation=_f(m.group(3)), kind='intermediate'))
            continue
        m = re.match(rf'^dTheta_int\s+({N}) vs ({N})\s+lam2 ({N}) vs ({N})', s)
        if m:
            rows.append(_row(f'{head} - dTheta_int (K)', _f(m.group(1)), _f(m.group(2)), unit='K', kind='intermediate'))
            rows.append(_row(f'{head} - lambda2', _f(m.group(3)), _f(m.group(4)), kind='intermediate'))
    return rows


def p_esf(text):
    rows = []
    for c, a, b, d in re.findall(rf'^(\S+\s+.+?)\s+({N})\s+({N})\s+({N})\s*$', text, re.M):
        if re.match(r'^[A-Z]-[A-Z]', c) and not re.search(r'\s(R|lam1|lam2|T\d)$', c.strip()):
            rows.append(_row(c.strip() + ' rating (A)', _f(a), _f(b), deviation=_f(d)))
    for c, q, a, b, d in re.findall(rf'^([A-Z]-[A-Z].+?)\s+(R|lam1|lam2|T1|T2|T3|T4)\s+({N})\s+({N})\s+(\S+)\s*$', text, re.M):
        a, b = _f(a), _f(b)
        dev = None if d in ('+nan', 'nan', '-nan') else _f(d)
        rows.append(_row(f'{c.strip()} - {q}', a, b, kind='intermediate', deviation=dev,
                         within_override=(True if dev is None and a == b else None)))
    return rows


PARSERS = {
    'mode4_validate': p_mode4, 'suite_validate': p_suite, 'emergency_validate': p_emergency,
    'mode4_cymcap_validate': p_m4cymcap, 'cymcap_ductbank_validate': p_cymcap_duct,
    'cymcap_3core_validate': p_3core, 'volta_validate': p_volta, 'transco_validate': p_transco,
    'soil_validate': p_soil, 'ground3c_validate': p_ground3c, 'ductbank_validate': p_ductbank,
    'esf_validate': p_esf,
}


def judge(case: dict, rows: list[dict], returned) -> str:
    tol_pct, tol_K = case.get('tol_pct'), case.get('tol_K')
    for r in rows:
        if r.get('flag'):
            r['tolerance'] = None
            r['within'] = r['flag'] == 'OK'
            continue
        if r.get('within_override') is not None:
            r['tolerance'] = 'equal at 2 dp' if r['unit'].startswith('abs') else 0
            r['within'] = bool(r['within_override'])
            continue
        tol = tol_K if r['unit'] == 'K' else (tol_pct if r['unit'] == '%' else None)
        r['tolerance'] = tol
        if tol is None or r['deviation'] is None or (isinstance(r['deviation'], float) and math.isnan(r['deviation'])):
            r['within'] = None
        else:
            # round to the routine's printed precision before judging
            r['within'] = abs(round(r['deviation'], 6)) <= tol + 1e-9
    if any(r.get('flag') == 'GAP' for r in rows):
        return 'KNOWN_GAPS'
    head = [r for r in rows if r['kind'] == 'headline' and r['within'] is not None]
    if isinstance(returned, bool) and not head:
        return 'PASS' if returned else 'OUTSIDE_TOLERANCE'
    if not head:
        return 'INFO'
    status = 'PASS' if all(r['within'] for r in head) else 'OUTSIDE_TOLERANCE'
    if isinstance(returned, bool) and returned is False:
        status = 'OUTSIDE_TOLERANCE'
    return status


def run_case(case_id: str) -> dict:
    case = CASE_BY_ID[case_id]
    fn = getattr(L, case['fn'])
    t0 = time.perf_counter()
    returned = None
    error = None
    with run_engine(answers=case.get('answers', [])) as run:
        try:
            returned = fn()
        except Exception as e:  # reported, never hidden
            error = f'{type(e).__name__}: {e}\n' + traceback.format_exc(limit=3)
    elapsed = time.perf_counter() - t0
    rows = []
    status = 'ERROR'
    if not error:
        try:
            rows = PARSERS[case_id](run.stdout)
        except Exception as e:  # parser bug must not masquerade as a result
            error = f'output parser failed: {e}'
        if not error:
            status = judge(case, rows, returned if isinstance(returned, bool) else None)
    head = [r for r in rows if r['kind'] == 'headline']
    inter = [r for r in rows if r['kind'] == 'intermediate']

    def worst(rs, unit):
        v = [abs(r['deviation']) for r in rs if r['unit'] == unit and isinstance(r.get('deviation'), (int, float))
             and not math.isnan(r['deviation'])]
        return max(v) if v else None
    return {
        'case_id': case_id, 'title': case['title'], 'function': case['fn'] + '()',
        'source': case['source'], 'benchmark_kind': case['kind'], 'note': case['note'],
        'tolerance_pct': case.get('tol_pct'), 'tolerance_K': case.get('tol_K'),
        'tolerance_source': case.get('tol_source'),
        'status': status, 'returned': returned if isinstance(returned, (bool, int, float, str)) else None,
        'rows': rows,
        'headline_outside': sum(1 for r in head if r.get('within') is False),
        'intermediate_outside': sum(1 for r in inter if r.get('within') is False),
        'worst_abs_deviation_pct': worst(head, '%'), 'worst_abs_deviation_K': worst(head, 'K'),
        'output': run.stdout, 'error': error,
        'elapsed_s': elapsed, 'engine_version': ENGINE_VERSION,
        'verification': 'source-provided benchmark (not independently verified by Cable-N)',
    }
