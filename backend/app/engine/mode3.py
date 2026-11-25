"""Mode 3 - current-rating verification of a client duct-bank / buried
arrangement. Mirrors legacy collect_multi_bank_inputs() + rate_site()."""
from __future__ import annotations

import re

from . import legacy_engine as L
from .mode1 import InputRejected
from .runtime import run_engine, to_jsonable, ENGINE_VERSION, latin1

DESIG_RE = re.compile(r'^([13])\s*x\s*(\d+)$')


def build_site(p: dict) -> tuple[dict, list[str]]:
    """Typed request -> the `site` dict collect_multi_bank_inputs() builds,
    with the same validation it applies at the prompt."""
    warnings = []
    site = {
        'installation': 'b' if p['installation'] == 'duct' else 'a',
        'n_banks': len(p['banks']),
        'soil_rho': float(p['soil_rho']),
        'soil_temp': float(p['soil_temp']),
        'backfill_rho': (float(p['backfill_rho']) if p.get('backfill_rho') not in (None, '') else None),
        'armored': bool(p['armored']),
        'material': 'a' if p['material'] == 'cu' else 'b',
        'banks': [], 'gaps': [],
    }
    if not 1 <= site['n_banks'] <= 3:
        raise InputRejected('Between 1 and 3 banks/groups are supported (as in the original).')
    if site['soil_temp'] >= L.CABLE_MAX_TEMP:
        raise InputRejected('Soil temperature at/above conductor limit.')
    if site['backfill_rho'] is not None:
        worst = max(site['soil_rho'], site['backfill_rho'])
        choice = p.get('rho_choice') or 'worst'
        site['rho_used'] = {'native': site['soil_rho'], 'envelope': site['backfill_rho']}.get(choice, worst)
    else:
        site['rho_used'] = site['soil_rho']

    for bi, b in enumerate(p['banks'], 1):
        rows, cols = int(b['rows']), int(b['cols'])
        if not (1 <= rows <= 6 and 1 <= cols <= 12):
            raise InputRejected(f'Bank {bi}: rows 1-6, columns 1-12.')
        bank = {'rows': rows, 'cols': cols, 'h_pitch': float(b['h_pitch']),
                'v_pitch': float(b.get('v_pitch') or 0.0) if rows > 1 else 0.0,
                'top_depth': float(b['top_depth']), 'positions': {}}
        if not 50 <= bank['h_pitch'] <= 2000:
            raise InputRejected(f'Bank {bi}: horizontal pitch must be 50-2000 mm.')
        if rows > 1 and not 50 <= bank['v_pitch'] <= 2000:
            raise InputRejected(f'Bank {bi}: vertical pitch must be 50-2000 mm.')
        if not 0.1 <= bank['top_depth'] <= 3.0:
            raise InputRejected(f'Bank {bi}: top-row depth must be 0.1-3.0 m.')
        for pos in b.get('positions', []):
            r, c = int(pos['row']), int(pos['col'])
            if not (1 <= r <= rows and 1 <= c <= cols):
                raise InputRejected(f'Bank {bi}: position R{r}-C{c} is outside the {rows}x{cols} grid.')
            m = DESIG_RE.match(str(pos['desig']).strip().lower())
            if not m:
                raise InputRejected(f"B{bi} R{r}-C{c}: designation must be 1x<size> or 3x<size>.")
            cfg = 'T3' if m.group(1) == '1' else 'C3'
            size = m.group(2)
            key, method, note = L.cfg_table_and_method(cfg, site['material'], site['armored'],
                                                       site['installation'])
            valid = sorted(L.base_current_tables[key][method], key=float)
            if size not in valid:
                raise InputRejected(f"B{bi} R{r}-C{c}: size {size} not in the "
                                    f"{'single-core' if cfg == 'T3' else '3-core'} table. "
                                    f"Valid: {', '.join(valid)}")
            load = pos.get('load')
            bank['positions'][(r, c)] = {'cfg': cfg, 'size': size, 'desig': f'{m.group(1)}x{size}',
                                         'load': float(load) if load not in (None, '') else None,
                                         'tkey': key, 'method': method, 'note': note}
        auto = len(bank['positions'])
        circ = b.get('circuits')
        bank['circuits'] = int(circ) if circ not in (None, '') else auto
        if not 0 <= bank['circuits'] <= 24:
            raise InputRejected(f'Bank {bi}: circuits for grouping must be 0-24.')
        if bank['circuits'] > 12:
            warnings.append(f'Bank {bi}: {bank["circuits"]} circuits exceeds the 12-circuit group '
                            'tables; the factor is capped at 12 (original behaviour).')
        site['banks'].append(bank)
    gaps = [float(g) for g in (p.get('gaps') or [])]
    if site['n_banks'] > 1:
        if len(gaps) != site['n_banks'] - 1:
            raise InputRejected('Enter one clear distance per pair of adjacent banks.')
        for g in gaps:
            if not 0.05 <= g <= 20:
                raise InputRejected('Bank gaps must be 0.05-20 m.')
    site['gaps'] = gaps
    ov = p.get('interbank_override')
    site['interbank_override'] = float(ov) if (site['n_banks'] > 1 and ov not in (None, '')) else 0.0
    if not 0 <= site['interbank_override'] <= 1:
        raise InputRejected('Inter-bank factor override must be 0-1.')
    if not any(b['positions'] for b in site['banks']):
        raise InputRejected('No cables entered - nothing to rate.')
    return site, warnings


def run_rating(p: dict) -> dict:
    site, warnings = build_site(p)
    with run_engine() as run:
        results = L.rate_site(site)
    out_rows = []
    for (bi, r, c), res in sorted(results.items()):
        out_rows.append(dict(to_jsonable(res), pos=f'B{bi}R{r}-C{c}', bank=bi, row=r, col=c,
                             config_label=res['desig'] + (' trefoil' if res['cfg'] == 'T3' else ' 3-core')))
    banks = []
    for bi, b in enumerate(site['banks'], 1):
        banks.append({'id': bi, 'rows': b['rows'], 'cols': b['cols'], 'h_pitch': b['h_pitch'],
                      'v_pitch': b['v_pitch'], 'top_depth': b['top_depth'],
                      'circuits': b['circuits'], 'cg': b['cg'], 'cg_note': b['cg_note'],
                      'spacing_key': b['spacing_key']})
    loaded = [r for r in out_rows if r.get('load') is not None]
    notes = sorted({r['note'] for r in out_rows if r.get('note')})
    return {
        'mode': 'current_rating',
        'engine_version': ENGINE_VERSION,
        'banks': banks,
        'gaps': site['gaps'],
        'inter': site['inter'], 'inter_note': site['inter_note'],
        'rho_used': site['rho_used'], 'soil_rho': site['soil_rho'],
        'backfill_rho': site['backfill_rho'], 'soil_temp': site['soil_temp'],
        'installation': p['installation'],
        'material': p['material'], 'armored': site['armored'],
        'positions': out_rows,
        'summary': {'positions': len(out_rows), 'loaded': len(loaded),
                    'overload': sum(1 for r in loaded if r['status'] == 'OVERLOAD'),
                    'min_rating': min(r['iz'] for r in out_rows)},
        'warnings': warnings + notes + run.warnings + [
            'This verifies CURRENT RATING only (table method). It does not check voltage drop, '
            'short-circuit withstand or any other requirement.'],
        'limitations': [
            'Each 2D bank is approximated as a horizontal group of its circuit count at the duct '
            'pitch; vertical mutual heating enters via the depth factor only.',
            'Group tables assume identical cables; mixed sizes share one Cg per bank.',
            'Where an envelope is present, the selected effective resistivity governs; two-region '
            'soil is not modelled.',
            'Verification-grade table ratings - a full IEC 60287 study is needed for guaranteed '
            'ampacities and conductor temperatures.'],
    }


def generate_pdf(p: dict, pdf_dir: str, project: dict) -> str:
    site, _ = build_site(p)
    with run_engine(answers=[latin1(project.get('name', '')), latin1(project.get('client', '')),
                             latin1(project.get('ref', ''))], pdf_dir=pdf_dir) as run:
        results = L.rate_site(site)
        L.generate_rating_pdf(site, results)
    if not run.pdf_file:
        raise RuntimeError('legacy rating PDF generator did not write a file')
    return run.pdf_file
