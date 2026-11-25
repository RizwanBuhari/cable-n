"""Calculation dispatch and result summarisation (stateless)."""
from __future__ import annotations

from ..engine import mode1, mode2, mode3, mode4
from ..schemas.calc import AdvancedIn, BatchIn, CurrentRatingIn, SingleFeederIn

MODES = {
    'single_feeder': ('Single feeder sizing', SingleFeederIn),
    'batch': ('Batch cable schedule', BatchIn),
    'current_rating': ('Current-rating verification', CurrentRatingIn),
    'advanced_mvhv': ('Advanced MV/HV analysis', AdvancedIn),
}


def validate_inputs(mode: str, inputs: dict) -> dict:
    model = MODES[mode][1]
    return model.model_validate(inputs).model_dump()


def compute(mode: str, inputs: dict, progress=None, cancelled=None) -> dict:
    if mode == 'single_feeder':
        return mode1.run_single_feeder(inputs)
    if mode == 'batch':
        return mode2.run_batch(inputs['common'], inputs['feeders'], inputs.get('arrangement'),
                               progress=progress, cancelled=cancelled)
    if mode == 'current_rating':
        return mode3.run_rating(inputs)
    if mode == 'advanced_mvhv':
        return mode4.run_full_report(inputs)
    raise ValueError(f'unknown mode {mode}')


def summarise(mode: str, inputs: dict, result: dict) -> dict:
    """Denormalised fields for dashboards and analytics."""
    s = {'voltage_v': None, 'material': None, 'installation': None, 'cable_size': None,
         'utilisation': None, 'outcome': None, 'failed_checks': 0, 'warnings_count': 0,
         'failure_categories': []}
    cats = []
    if mode == 'single_feeder':
        s['voltage_v'] = inputs['voltage']
        s['material'] = inputs['material'].upper()
        s['installation'] = inputs['installation']
        s['outcome'] = result['status']
        if result['single']:
            r = result['single']['recommended']
            s['cable_size'] = r['size']
            s['utilisation'] = r['utilisation']
            if r['sc_status'] == 'FAIL':
                cats.append('short-circuit')
        elif result['best_by_spacing']:
            b = min(result['best_by_spacing'], key=lambda x: (x['runs'], float(x['size'])))
            s['cable_size'] = f"{b['runs']}x{b['size']}"
            s['utilisation'] = b['utilisation']
            cats.append('single-run infeasible')
        else:
            cats.append('no feasible configuration')
    elif mode == 'batch':
        c = inputs['common']
        s['voltage_v'] = c['voltage']; s['material'] = c['material'].upper()
        s['installation'] = c['installation']
        sm = result['summary']
        s['outcome'] = 'feasible' if sm['no_solution'] == 0 and sm['invalid'] == 0 else 'partial'
        if sm['no_solution']:
            cats.append('no feasible configuration')
        if sm['sc_fail']:
            cats.append('short-circuit')
        if sm['invalid']:
            cats.append('invalid input rows')
        utils = [r['rec']['utilisation'] for r in result['rows'] if r.get('rec')]
        s['utilisation'] = max(utils) if utils else None
        s['cable_size'] = f"{sm['calculated']} feeders"
    elif mode == 'current_rating':
        s['material'] = inputs['material'].upper()
        s['installation'] = inputs['installation']
        sm = result['summary']
        s['outcome'] = 'overload' if sm['overload'] else 'rated'
        if sm['overload']:
            cats.append('overload')
        utils = [p['util'] for p in result['positions'] if p.get('util') is not None]
        s['utilisation'] = max(utils) if utils else None
    elif mode == 'advanced_mvhv':
        s['voltage_v'] = max(c['U'] for c in result['cables']) * 1000
        s['material'] = result['cables'][0]['mat']
        s['installation'] = result['installation']
        s['cable_size'] = ', '.join(sorted({c['desig'] for c in result['cables']}))
        over = [p for p in result['placed'] if p.get('over_limit')]
        s['outcome'] = 'over_temperature' if over else 'rated'
        if over:
            cats.append('over temperature')
        if any(not r['short_circuit']['adequate'] for r in result['reports']):
            cats.append('short-circuit')
        if any(r['induced']['V_tref'] > 65 for r in result['reports']):
            cats.append('sheath voltage')
    checks = result.get('checks') or []
    s['failed_checks'] = sum(1 for c in checks if c['status'] == 'FAIL') + len(cats)
    s['failure_categories'] = sorted(set(cats))
    s['warnings_count'] = len(result.get('warnings') or [])
    return s
