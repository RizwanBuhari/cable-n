"""Mode 1 - single feeder sizing study.

Mirrors legacy interactive_main() step for step (same functions, same
order, same selection rules) but takes a typed input dict instead of terminal
answers and returns a structured result instead of printing.
"""
from __future__ import annotations

from collections import defaultdict

from . import legacy_engine as L
from .runtime import run_engine, to_jsonable, ENGINE_VERSION

SPACINGS = ['Touching', '200', '400', '600', '800']


class InputRejected(ValueError):
    """Input combination the engine would accept but which would give a
    misleading result. Raised instead of computing."""


# ---------------------------------------------------------------- inputs
def to_legacy_inputs(p: dict) -> dict:
    """Typed request -> the exact dict get_user_input() builds."""
    inp = {
        'voltage': float(p['voltage']),
        'voltage_drop_limit': float(p['voltage_drop_limit_pct']) / 100.0,
        'power_factor': float(p['power_factor']),
        'core_type': 'a' if p['core_type'] == '1C' else 'b',
        'armored': bool(p['armored']),
        'material': 'a' if p['material'] == 'cu' else 'b',
        'phase': 'a' if p['phase'] == 'single' else 'b',
        'cable_length': float(p['cable_length']),
    }
    if 'insulation' in p and p['insulation'] is not None:
        inp['insulation'] = p['insulation']
        inp['max_temp'] = 90 if p['insulation'] == 'xlpe' else 70
    if p['load_mode'] == 'current':
        inp['current'] = float(p['current'])
    else:
        inp['power'] = float(p['power'])
        inp['power_unit'] = p['power_unit'].upper()
    inst = p['installation']
    if inst == 'buried':
        inp['installation'] = 'a'
        inp['soil_resistivity'] = float(p['soil_resistivity'])
        inp['soil_temp'] = float(p['soil_temp'])
        inp['depth'] = float(p['depth'])
    elif inst == 'duct':
        inp['installation'] = 'b'
        inp['duct_resistivity'] = float(p['duct_resistivity'])
        inp['soil_temp'] = float(p['soil_temp'])
        inp['depth'] = float(p['depth'])
    else:
        inp['installation'] = 'c'
        inp['air_temp'] = float(p['air_temp'])
    if p.get('sc_check'):
        inp['fault_kA'] = float(p['fault_kA'])
        inp['fault_time'] = float(p['fault_time'])
        inp['fault_share'] = p.get('fault_share') or 'equal'
    return inp


def table_key_for(inp: dict) -> str:
    material_str = 'CU' if inp['material'] == 'a' else 'AL'
    armor_str = 'ARMOURED' if inp['armored'] else 'UNARMOURED'
    core_str = 'SINGLE' if inp['core_type'] == 'a' else '3CORE'
    return f'{material_str}_{armor_str}_{core_str}'


def arrangement_options(inp: dict, table_key: str) -> list[str]:
    """Same filter as legacy select_arrangement()."""
    prefix = L.INSTALL_PREFIX[inp['installation']]
    return [k for k in L.base_current_tables[table_key].keys() if k.startswith(prefix)]


def check_inputs(inp: dict) -> list[str]:
    """Blocks combinations that would divide by zero or silently clamp to a
    meaningless factor. Returns advisory warnings for the ones that remain
    valid but approximate."""
    warnings = []
    if 'power' in inp and inp['power_unit'] in ('KW', 'MW') and inp['power_factor'] <= 0:
        raise InputRejected('Power factor must be greater than 0 when the load is given in kW or MW '
                            '(the design current divides by it).')
    tmax = inp.get('max_temp', L.CABLE_MAX_TEMP)
    amb = inp['air_temp'] if inp['installation'] == 'c' else inp['soil_temp']
    if amb >= tmax:
        raise InputRejected(f'Ambient temperature {amb} C is at or above the conductor limit {tmax} C; '
                            'the original engine would substitute Ca = 0.01, which is not a valid rating.')
    if inp.get('insulation') == 'pvc':
        warnings.append('PVC selected: base ampacity tables are 90 C XLPE ratings. The original engine '
                        'applies Tmax = 70 C in Ca and an extra x0.90 construction factor - an '
                        'approximation; verify against PVC ampacity tables.')
    if inp['installation'] in ('a', 'b'):
        rho = inp.get('soil_resistivity') if inp['installation'] == 'a' else inp.get('duct_resistivity')
        lo, hi = 0.7, 3.0
        if rho < lo or rho > hi:
            warnings.append(f'Thermal resistivity {rho} K.m/W is outside the rating-factor table '
                            f'({lo}-{hi}); the engine uses the nearest tabled value (no extrapolation).')
        if inp['depth'] < 0.5 or inp['depth'] > 3.0:
            warnings.append(f"Depth {inp['depth']} m is outside the depth-factor table (0.5-3.0 m); "
                            'nearest tabled value used.')
        warnings.append('Rating-factor tables use nearest-value lookup (no interpolation), as in the '
                        'original engine.')
    if 'fault_kA' in inp and inp.get('fault_share') == 'equal':
        warnings.append('Short-circuit check for parallel runs assumes the fault current shares '
                        'equally between runs.')
    return warnings


# ---------------------------------------------------------------- run
def _sol(sol: dict) -> dict:
    return to_jsonable(sol)


def run_single_feeder(p: dict) -> dict:
    inp = to_legacy_inputs(p)
    adapter_warnings = check_inputs(inp)
    table_key = table_key_for(inp)
    if table_key not in L.base_current_tables:
        raise InputRejected(f'No base current table for {table_key}')
    options = arrangement_options(inp, table_key)
    if not options:
        raise InputRejected(f'No rated arrangement for this installation in table {table_key}')
    arrangement = p.get('arrangement') or options[0]
    if arrangement not in options:
        raise InputRejected(f'Arrangement {arrangement} is not rated for {table_key}; options: {options}')

    with run_engine() as run:
        ib = L.calculate_current(inp)
        singles, rejections = L.find_single_run_solutions(inp, table_key, arrangement, ib)
        multi = L.find_multi_run_solutions(inp, table_key, arrangement, ib, SPACINGS)
        best_by_spacing = {}
        if multi:
            for sp in SPACINGS:
                cands = [s for sols in multi.values() for s in sols if s['spacing'] == sp]
                if cands:
                    best_by_spacing[sp], _ = L.pick_recommended(
                        cands, key=lambda x: (x['runs'], float(x['size'])))
        all_options = L.find_all_run_options(inp, table_key, arrangement, ib, SPACINGS) if multi else {}

        best_single, all_fail = L.pick_recommended(singles)
        single_block = None
        if singles:
            single_block = {
                'recommended': _sol(best_single),
                'all_fail_short_circuit': all_fail,
                'circuit': L.circuit_description(inp, best_single),
                'governing': L.governing_constraint(inp, table_key, arrangement, best_single, ib),
                'chain': L.chain_string(best_single),
                'exclusions': L.summarize_exclusions(rejections, singles, best_single),
                'solutions': [dict(_sol(s), recommended=(s is best_single))
                              for s in sorted(singles, key=lambda x: float(x['size']))],
            }
        best_list = []
        for sp in SPACINGS:
            if sp in best_by_spacing:
                s = best_by_spacing[sp]
                best_list.append(dict(_sol(s),
                                      circuit=L.circuit_description(inp, s),
                                      governing=L.governing_constraint(inp, table_key, arrangement, s, ib),
                                      chain=L.chain_string(s)))
        sizes = sorted(L.base_current_tables[table_key][arrangement], key=float)
        matrix = []
        for size in sizes:
            row = {'size': size, 'cells': {}}
            for sp in SPACINGS:
                cell = L.matrix_cell(multi, size, sp)
                row['cells'][sp] = None if cell is None else {
                    'runs': cell['runs'], 'utilisation': cell['utilisation'],
                    'sc_status': cell['sc_status'],
                    'recommended': best_by_spacing.get(sp) is cell}
            matrix.append(row)
        detailed = {sp: [dict(_sol(s), recommended=L._is_recommended(s, best_by_spacing))
                         for s in sols] for sp, sols in all_options.items()}
        derating_by_size = {size: L.calculate_derating_factors(inp, size) for size in sizes}
        install_desc = L.installation_description(inp, arrangement)

    status = 'feasible' if (singles or best_by_spacing) else 'no_solution'
    checks = []
    if single_block:
        r = single_block['recommended']
        checks.append({'name': 'Ampacity (Ib <= Iz)', 'status': 'PASS',
                       'detail': f"Iz {r['derated_current']:.1f} A >= Ib {ib:.1f} A"})
        checks.append({'name': 'Voltage drop', 'status': 'PASS',
                       'detail': f"{r['voltage_drop']:.2f}% <= {inp['voltage_drop_limit']*100:.2f}%"})
        if r['sc_status']:
            checks.append({'name': 'Short-circuit withstand', 'status': r['sc_status'],
                           'detail': f"{r['short_circuit']:.2f} kA vs {r['sc_required']:.2f} kA required"})
        else:
            checks.append({'name': 'Short-circuit withstand', 'status': 'NOT_CHECKED',
                           'detail': 'No prospective fault level entered'})
    elif best_list:
        checks.append({'name': 'Single run', 'status': 'FAIL',
                       'detail': 'No single-run size meets ampacity and voltage drop; parallel runs required'})
    else:
        checks.append({'name': 'Any configuration', 'status': 'FAIL',
                       'detail': 'No configuration in the rated range meets all criteria'})

    return {
        'mode': 'single_feeder',
        'engine_version': ENGINE_VERSION,
        'status': status,
        'design_current': ib,
        'legacy_inputs': to_jsonable(inp),
        'table_key': table_key,
        'arrangement': arrangement,
        'arrangement_label': L.ARRANGEMENT_LABELS.get(arrangement, arrangement),
        'arrangement_options': [{'key': k, 'label': L.ARRANGEMENT_LABELS.get(k, k)} for k in options],
        'installation_description': install_desc,
        'has_sc': 'fault_kA' in inp,
        'single': single_block,
        'rejections': rejections,
        'best_by_spacing': best_list,
        'matrix': matrix,
        'detailed_options': detailed,
        'derating_by_size': to_jsonable(derating_by_size),
        'checks': checks,
        'warnings': adapter_warnings + run.warnings,
        'engine_messages': run.messages,
        'basis': [L.FACTOR_SOURCES[k] for k in ('ambient', 'soil', 'depth', 'group', 'sc')],
        'constants': {'CABLE_MAX_TEMP': L.CABLE_MAX_TEMP, 'REF_TEMP_GROUND': L.REF_TEMP_GROUND,
                      'REF_TEMP_AIR': L.REF_TEMP_AIR, 'K_ADIABATIC': L.K_ADIABATIC,
                      'max_temp_used': inp.get('max_temp', L.CABLE_MAX_TEMP)},
        'spacings': SPACINGS,
    }


def options_for(p: dict) -> list[dict]:
    """Arrangements available for a partial input (core/material/armour/installation)."""
    inp = {'material': 'a' if p['material'] == 'cu' else 'b', 'armored': bool(p['armored']),
           'core_type': 'a' if p['core_type'] == '1C' else 'b',
           'installation': {'buried': 'a', 'duct': 'b', 'air': 'c'}[p['installation']]}
    tk = table_key_for(inp)
    return [{'key': k, 'label': L.ARRANGEMENT_LABELS.get(k, k),
             'sizes': sorted(L.base_current_tables[tk][k], key=float)}
            for k in arrangement_options(inp, tk)]


def generate_pdf(p: dict, result: dict, pdf_dir: str, project: dict) -> str:
    """Runs the ORIGINAL generate_pdf_report() unchanged; its terminal prompts
    (project, client, ref, 'open now?') are answered from `project`."""
    inp = to_legacy_inputs(p)
    table_key = result['table_key']
    arrangement = result['arrangement']
    from .runtime import latin1
    answers = [latin1(project.get('name', '')), latin1(project.get('client', '')),
               latin1(project.get('ref', '')), 'n']
    with run_engine(answers=answers, pdf_dir=pdf_dir) as run:
        ib = L.calculate_current(inp)
        singles, rejections = L.find_single_run_solutions(inp, table_key, arrangement, ib)
        multi = L.find_multi_run_solutions(inp, table_key, arrangement, ib, SPACINGS)
        best_by_spacing = {}
        if multi:
            for sp in SPACINGS:
                cands = [s for sols in multi.values() for s in sols if s['spacing'] == sp]
                if cands:
                    best_by_spacing[sp], _ = L.pick_recommended(
                        cands, key=lambda x: (x['runs'], float(x['size'])))
        L.generate_pdf_report(inp, ib, table_key, arrangement, singles,
                              multi if multi else defaultdict(list), best_by_spacing,
                              rejections=rejections)
    if not run.pdf_file:
        raise RuntimeError('legacy report generator did not write a PDF: ' + run.stdout[-500:])
    return run.pdf_file
