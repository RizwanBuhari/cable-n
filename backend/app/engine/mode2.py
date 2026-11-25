"""Mode 2 - batch cable schedule. Mirrors legacy batch_main(): common
parameters once, then size_feeder() for every feeder (single run preferred,
parallel-run fallback), exactly as the original."""
from __future__ import annotations

from . import legacy_engine as L
from .mode1 import InputRejected, table_key_for, arrangement_options
from .runtime import run_engine, to_jsonable, ENGINE_VERSION, latin1


def common_to_legacy(c: dict) -> dict:
    """Same keys collect_common_inputs() produces. Note the original batch mode
    never asks insulation or fault sharing: XLPE ratings and equal sharing are
    therefore what it uses, and so does this adapter."""
    out = {
        'voltage': float(c['voltage']),
        'phase': 'a' if c['phase'] == 'single' else 'b',
        'voltage_drop_limit': float(c['voltage_drop_limit_pct']) / 100.0,
        'power_factor': float(c['power_factor']),
        'core_type': 'a' if c['core_type'] == '1C' else 'b',
        'armored': bool(c['armored']),
        'material': 'a' if c['material'] == 'cu' else 'b',
    }
    inst = c['installation']
    if inst == 'buried':
        out.update(installation='a', soil_resistivity=float(c['soil_resistivity']),
                   soil_temp=float(c['soil_temp']), depth=float(c['depth']))
    elif inst == 'duct':
        out.update(installation='b', duct_resistivity=float(c['duct_resistivity']),
                   soil_temp=float(c['soil_temp']), depth=float(c['depth']))
    else:
        out.update(installation='c', air_temp=float(c['air_temp']))
    if c.get('sc_check'):
        out['fault_kA'] = float(c['fault_kA'])
        out['fault_time'] = float(c['fault_time'])
    return out


def feeder_to_legacy(f: dict, common: dict | None = None) -> dict:
    """collect_feeders() always stores power_factor and voltage_drop_limit on
    the feeder: a blank answer returns the common default, and the VD default
    goes through (common*100)/100. Reproduced exactly so results are
    bit-identical to the original."""
    out = {'tag': (f.get('tag') or '').strip() or 'F-??',
           'cable_length': float(f['cable_length'])}
    if common is not None:
        out['power_factor'] = common['power_factor']
        out['voltage_drop_limit'] = (common['voltage_drop_limit'] * 100) / 100
    if f.get('load_mode', 'current') == 'current':
        out['current'] = float(f['current'])
    else:
        out['power'] = float(f['power'])
        out['power_unit'] = f['power_unit'].upper()
    if f.get('power_factor') is not None:
        out['power_factor'] = float(f['power_factor'])
    if f.get('voltage_drop_limit_pct') is not None:
        out['voltage_drop_limit'] = float(f['voltage_drop_limit_pct']) / 100.0
    return out


def validate_feeder(f: dict, common: dict) -> list[str]:
    errs = []
    lm = f.get('load_mode', 'current')
    if lm == 'current':
        if f.get('current') is None or float(f['current']) <= 0:
            errs.append('Load current must be > 0 A')
    else:
        if f.get('power') is None or float(f['power']) <= 0:
            errs.append('Power must be > 0')
        if (f.get('power_unit') or '').upper() not in ('KW', 'KVA', 'MW', 'MVA'):
            errs.append('Unit must be kW, kVA, MW or MVA')
        pf = f.get('power_factor') if f.get('power_factor') is not None else common['power_factor']
        if (f.get('power_unit') or '').upper() in ('KW', 'MW') and float(pf) <= 0:
            errs.append('Power factor must be > 0 for kW/MW loads')
    if f.get('cable_length') is None or float(f['cable_length']) < 0.1:
        errs.append('Route length must be at least 0.1 m')
    pf = f.get('power_factor')
    if pf is not None and not (0 <= float(pf) <= 1):
        errs.append('Power factor must be between 0 and 1')
    vd = f.get('voltage_drop_limit_pct')
    if vd is not None and not (0 <= float(vd) <= 100):
        errs.append('Voltage drop limit must be 0-100 %')
    return errs


def _row(r: dict) -> dict:
    rec = r['rec']
    out = {
        'tag': r['tag'], 'ib': r['ib'], 'all_fail': r['all_fail'],
        'governing': r['governing'], 'exclusions': r['exclusions'],
        'multi_fallback': r['multi_fallback'],
        'rec': to_jsonable(rec),
        'candidates': to_jsonable(r['candidates']),
        'spacing_variants': to_jsonable(r['spacing_variants']),
        'feeder_inputs': to_jsonable({k: v for k, v in r['inputs'].items()
                                      if k in ('current', 'power', 'power_unit', 'cable_length',
                                               'power_factor', 'voltage_drop_limit')}),
    }
    if rec:
        out['circuit'] = L.circuit_description(r['inputs'], rec)
        out['chain'] = L.chain_string(rec)
        if rec['sc_status'] == 'FAIL':
            out['status'] = 'sc_fail'
        else:
            out['status'] = 'ok'
    else:
        out['status'] = 'no_solution'
    return out


def run_batch(common_in: dict, feeders_in: list[dict], arrangement: str | None,
              progress=None, cancelled=None) -> dict:
    common = common_to_legacy(common_in)
    tmax = L.CABLE_MAX_TEMP
    amb = common['air_temp'] if common['installation'] == 'c' else common['soil_temp']
    if amb >= tmax:
        raise InputRejected(f'Ambient {amb} C is at/above the conductor limit {tmax} C.')
    tk = table_key_for(common)
    if tk not in L.base_current_tables:
        raise InputRejected(f'No base current table for {tk}')
    opts = arrangement_options(common, tk)
    if not opts:
        raise InputRejected('No rated arrangement for this installation')
    arrangement = arrangement or opts[0]
    if arrangement not in opts:
        raise InputRejected(f'Arrangement {arrangement} not rated; options {opts}')

    rows, invalid, messages = [], [], []
    seen = set()
    total = len(feeders_in)
    for i, f in enumerate(feeders_in):
        if cancelled and cancelled():
            break
        errs = validate_feeder(f, common)
        tag = (f.get('tag') or f'F-{i+1:02d}').strip()
        if tag in seen:
            errs.append(f'Duplicate feeder tag {tag}')
        seen.add(tag)
        if errs:
            invalid.append({'index': i, 'tag': tag, 'errors': errs})
        else:
            lf = feeder_to_legacy(dict(f, tag=tag), common)
            with run_engine() as run:
                r = L.size_feeder(common, lf, tk, arrangement)
            row = _row(r)
            row['index'] = i
            row['name'] = f.get('name') or ''
            row['engine_messages'] = run.messages
            rows.append(row)
            messages += [f'{tag}: {m}' for m in run.warnings]
        if progress:
            progress(i + 1, total)

    return {
        'mode': 'batch',
        'engine_version': ENGINE_VERSION,
        'table_key': tk,
        'arrangement': arrangement,
        'arrangement_label': L.ARRANGEMENT_LABELS.get(arrangement, arrangement),
        'arrangement_options': [{'key': k, 'label': L.ARRANGEMENT_LABELS.get(k, k)} for k in opts],
        'installation_description': L.installation_description(common, arrangement),
        'construction': (f"{'Cu' if common['material']=='a' else 'Al'}/"
                         f"{'1C' if common['core_type']=='a' else '3C'}/XLPE"
                         f"{'/SWA' if common['armored'] else ''}"),
        'has_sc': 'fault_kA' in common,
        'legacy_common': to_jsonable(common),
        'rows': rows,
        'invalid_rows': invalid,
        'summary': {
            'total': total, 'calculated': len(rows), 'invalid': len(invalid),
            'no_solution': sum(1 for r in rows if r['status'] == 'no_solution'),
            'sc_fail': sum(1 for r in rows if r['status'] == 'sc_fail'),
            'parallel_fallback': sum(1 for r in rows if r['multi_fallback']),
        },
        'warnings': (['Batch mode (as in the original) uses XLPE 90 C ratings and assumes equal '
                      'fault sharing between parallel runs.'] + messages),
    }


def generate_pdf(common_in: dict, feeders_in: list[dict], arrangement: str, pdf_dir: str,
                 project: dict) -> str:
    common = common_to_legacy(common_in)
    tk = table_key_for(common)
    rows = []
    with run_engine(answers=[latin1(project.get('name', '')), latin1(project.get('client', '')),
                             latin1(project.get('ref', ''))], pdf_dir=pdf_dir) as run:
        for i, f in enumerate(feeders_in):
            if validate_feeder(f, common):
                continue
            tag = latin1((f.get('tag') or f'F-{i+1:02d}').strip())
            rows.append(L.size_feeder(common, feeder_to_legacy(dict(f, tag=tag), common), tk, arrangement))
        L.generate_batch_pdf(common, rows, tk, arrangement)
    if not run.pdf_file:
        raise RuntimeError('legacy batch PDF generator did not write a file')
    return run.pdf_file
