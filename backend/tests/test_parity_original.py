"""Numerical parity with the ORIGINAL program (not with a copy of it).

Each test drives the untouched reference/original_engine/cable_sizing_FINAL.py
through its real terminal dialogue with scripted answers, records what its
own functions return, and requires the Cable-N adapter to produce the SAME
values for the equivalent typed request. Tolerance: exact equality (both
sides execute the same arithmetic); floats are compared with
math.isclose(rel_tol=1e-12) only to absorb representation of re-parsed
string answers."""
import math

import pytest

from app.engine import mode1, mode2, mode3, mode4
from app.engine.runtime import to_jsonable
from tests.original_driver import Driver, mode1_answers, mode2_answers, mode3_answers, mode4_answers

REL = 1e-12


def same(a, b, path='$'):
    a, b = to_jsonable(a), to_jsonable(b)
    if isinstance(a, float) or isinstance(b, float):
        assert a is not None and b is not None, f'{path}: {a} vs {b}'
        assert math.isclose(float(a), float(b), rel_tol=REL, abs_tol=1e-12), f'{path}: {a} != {b}'
    elif isinstance(a, dict):
        assert set(a) == set(b), f'{path}: keys {sorted(set(a) ^ set(b))}'
        for k in a:
            same(a[k], b[k], f'{path}.{k}')
    elif isinstance(a, list):
        assert len(a) == len(b), f'{path}: len {len(a)} != {len(b)}'
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f'{path}[{i}]')
    else:
        assert a == b, f'{path}: {a!r} != {b!r}'


# ------------------------------------------------------------------ Mode 1
M1_CASES = [
    dict(voltage=415, voltage_drop_limit_pct=5, power_factor=0.85, phase='three', load_mode='current', current=250,
         insulation='xlpe', core_type='3C', armored=True, material='cu', installation='buried', soil_resistivity=1.5,
         soil_temp=30, depth=0.8, cable_length=150, sc_check=True, fault_kA=25, fault_time=1, fault_share='equal'),
    dict(voltage=11000, voltage_drop_limit_pct=3, power_factor=0.9, phase='three', load_mode='power', power=8,
         power_unit='MVA', insulation='xlpe', core_type='1C', armored=False, material='al', installation='duct',
         duct_resistivity=1.2, soil_temp=35, depth=1.0, cable_length=900, sc_check=True, fault_kA=31.5,
         fault_time=1, fault_share='full'),
    dict(voltage=400, voltage_drop_limit_pct=4, power_factor=0.8, phase='three', load_mode='power', power=1.2,
         power_unit='MW', insulation='xlpe', core_type='1C', armored=True, material='cu', installation='air',
         air_temp=45, cable_length=250, sc_check=False),
    dict(voltage=230, voltage_drop_limit_pct=3, power_factor=0.95, phase='single', load_mode='power', power=18,
         power_unit='KW', insulation='pvc', core_type='3C', armored=False, material='cu', installation='air',
         air_temp=35, cable_length=60, sc_check=True, fault_kA=6, fault_time=0.4, fault_share='equal'),
    dict(voltage=690, voltage_drop_limit_pct=5, power_factor=0.85, phase='three', load_mode='current', current=1800,
         insulation='xlpe', core_type='1C', armored=False, material='cu', installation='buried', soil_resistivity=2.5,
         soil_temp=35, depth=1.2, cable_length=400, sc_check=True, fault_kA=50, fault_time=1, fault_share='equal'),
    dict(voltage=415, voltage_drop_limit_pct=2.5, power_factor=0.85, phase='three', load_mode='power', power=600,
         power_unit='KVA', insulation='xlpe', core_type='3C', armored=True, material='al', installation='duct',
         duct_resistivity=0.8, soil_temp=25, depth=0.6, cable_length=320, sc_check=False),
]


def _m1_run_original(p, arr_index):
    d = Driver()
    for fn in ('get_user_input', 'calculate_current', 'find_single_run_solutions', 'find_multi_run_solutions',
               'select_arrangement'):
        d.spy(fn)
    out = d.run('interactive_main', mode1_answers(p, arr_index))
    return d, out


@pytest.mark.parametrize('p', M1_CASES)
def test_mode1_matches_original_for_every_arrangement(p):
    inp = mode1.to_legacy_inputs(p)
    tk = mode1.table_key_for(inp)
    options = mode1.arrangement_options(inp, tk)
    assert options
    for idx, arr in enumerate(options, 1):
        d, out = _m1_run_original(p, idx if len(options) > 1 else None)
        same(d.calls['get_user_input'][0]['out'], inp, '$inputs')
        assert d.calls['select_arrangement'][0]['out'] == arr
        res = mode1.run_single_feeder(dict(p, arrangement=arr))
        same(d.calls['calculate_current'][0]['out'], res['design_current'], '$ib')
        singles, _rej = d.calls['find_single_run_solutions'][0]['out']
        got = (res['single'] or {}).get('solutions', [])
        same(sorted(singles, key=lambda x: float(x['size'])),
             [{k: v for k, v in s.items() if k != 'recommended'} for s in got], '$singles')
        multi = d.calls['find_multi_run_solutions'][0]['out']
        # best per spacing exactly as interactive_main prints it
        for b in res['best_by_spacing']:
            line = f"{b['spacing']:>8}: {b['runs']} x {b['size']}mm2 | Iz {b['derated_current']:.1f}A"
            assert line in out, f'best-by-spacing line missing from original output: {line}'
        assert bool(multi) == bool(res['matrix'] and any(any(c for c in r['cells'].values()) for r in res['matrix']))
        if res['single']:
            r = res['single']['recommended']
            assert f"Single circuit: {res['single']['circuit']}" in out
            assert f"- Voltage drop: {r['voltage_drop']:.2f}%" in out
            assert f"- Governing constraint: {res['single']['governing']}" in out


# ------------------------------------------------------------------ Mode 2
M2_COMMON = [
    dict(voltage=415, phase='three', voltage_drop_limit_pct=5, power_factor=0.85, core_type='3C', armored=True,
         material='cu', installation='buried', soil_resistivity=1.5, soil_temp=30, depth=0.8, sc_check=True,
         fault_kA=25, fault_time=1),
    dict(voltage=400, phase='three', voltage_drop_limit_pct=4, power_factor=0.9, core_type='1C', armored=False,
         material='al', installation='air', air_temp=40, sc_check=False),
]
M2_FEEDERS = [
    dict(tag='P-101', load_mode='current', current=120, cable_length=150),
    dict(tag='P-102', load_mode='power', power=250, power_unit='KW', cable_length=300, power_factor=0.8),
    dict(tag='MCC-1', load_mode='power', power=1.5, power_unit='MVA', cable_length=90, voltage_drop_limit_pct=2.5),
    dict(tag='LTG', load_mode='current', current=35, cable_length=420),
    dict(tag='BIG', load_mode='current', current=2600, cable_length=600),
]


@pytest.mark.parametrize('common', M2_COMMON)
def test_mode2_matches_original(common):
    lc = mode2.common_to_legacy(common)
    tk = mode1.table_key_for(lc)
    options = mode1.arrangement_options(lc, tk)
    arr = options[0]
    d = Driver()
    d.spy('size_feeder')
    d.spy('collect_common_inputs')
    d.run('batch_main', mode2_answers(common, M2_FEEDERS, 1 if len(options) > 1 else None))
    same(d.calls['collect_common_inputs'][0]['out'], lc, '$common')
    res = mode2.run_batch(common, M2_FEEDERS, arr)
    orig_rows = [c['out'] for c in d.calls['size_feeder']]
    assert len(orig_rows) == len(res['rows'])
    for o, r in zip(orig_rows, res['rows']):
        assert o['tag'] == r['tag']
        same(o['ib'], r['ib'], f"{o['tag']}.ib")
        same(o['rec'], r['rec'], f"{o['tag']}.rec")
        assert o['governing'] == r['governing']
        assert o['exclusions'] == r['exclusions']
        assert o['multi_fallback'] == r['multi_fallback']
        same(o['spacing_variants'], r['spacing_variants'], f"{o['tag']}.variants")
        same(o['candidates'], r['candidates'], f"{o['tag']}.candidates")


# ------------------------------------------------------------------ Mode 3
M3_CASES = [
    dict(installation='duct', soil_rho=1.5, soil_temp=35, armored=True, material='cu',
         banks=[dict(rows=2, cols=3, h_pitch=250, v_pitch=250, top_depth=1.0,
                     positions=[dict(row=1, col=1, desig='3x240', load=300), dict(row=1, col=2, desig='1x630', load=500),
                                dict(row=2, col=3, desig='3x185')])]),
    dict(installation='buried', soil_rho=2.0, soil_temp=30, backfill_rho=1.0, rho_choice='envelope', armored=False,
         material='al', interbank_override=None, gaps=[1.5],
         banks=[dict(rows=1, cols=3, h_pitch=400, top_depth=0.9,
                     positions=[dict(row=1, col=1, desig='1x300', load=350), dict(row=1, col=3, desig='1x300')]),
                dict(rows=1, cols=2, h_pitch=300, top_depth=0.9, circuits=3,
                     positions=[dict(row=1, col=1, desig='3x150', load=180), dict(row=1, col=2, desig='3x150')])]),
    dict(installation='duct', soil_rho=1.2, soil_temp=40, backfill_rho=2.2, rho_choice='worst', armored=True,
         material='cu', gaps=[0.5, 2.0], interbank_override=0.85,
         banks=[dict(rows=1, cols=2, h_pitch=300, top_depth=1.2, positions=[dict(row=1, col=1, desig='1x500')]),
                dict(rows=2, cols=2, h_pitch=300, v_pitch=300, top_depth=1.2,
                     positions=[dict(row=2, col=2, desig='3x95', load=150)]),
                dict(rows=1, cols=1, h_pitch=300, top_depth=1.5, positions=[dict(row=1, col=1, desig='3x300')])]),
]


@pytest.mark.parametrize('p', M3_CASES)
def test_mode3_matches_original(p):
    d = Driver()
    d.spy('rate_site')
    d.run('rating_main', mode3_answers(p))
    call = d.calls['rate_site'][0]
    site_orig, res_orig = call['args'][0], call['out']
    site, _ = mode3.build_site(p)
    from app.engine import legacy_engine as L
    res = L.rate_site(site)
    same({str(k): v for k, v in res_orig.items()}, {str(k): v for k, v in res.items()}, '$results')
    same({k: v for k, v in site_orig.items() if k != 'banks'}, {k: v for k, v in site.items() if k != 'banks'}, '$site')
    api = mode3.run_rating(p)
    for row in api['positions']:
        o = res_orig[(row['bank'], row['row'], row['col'])]
        same(o['iz'], row['iz'], row['pos'])


# ------------------------------------------------------------------ Mode 4
C630 = mode4.PRESETS['mv_33kv_1x630_awa']['cable']
C132 = mode4.PRESETS['ref_132kv_1x400']['cable']
C3SL = mode4.PRESETS['mv_33kv_3x240_sl']['cable']
M4_CASES = [
    dict(standard='IEC', cables=[C630], installation='buried', tg=None,
         buried=dict(rho_e=1.2, L=1000, circuits=[dict(type=0, x=0, formation='trefoil'),
                                                  dict(type=0, x=600, formation='trefoil')]),
         Lroute=1000, If_sc=31.5, emergency=True),
    dict(standard='IEC', cables=[C132], installation='buried', tg=35,
         buried=dict(rho_e=1.5, L=1300, backfill_rho=1.0,
                     circuits=[dict(type=0, x=0, formation='flat_spaced', spacing=300)]),
         Lroute=800, If_sc=40, emergency=False, rho_earth=50, t_sc=0.5),
    dict(standard='IEC', cables=[C630, C3SL], installation='duct',
         duct=dict(rho_e=1.2, Do=200, Dd=180, fill='filled', rho_fill=1.2, n_in_duct=3, soil_model='bank',
                   rho_native=2.0,
                   banks=[dict(rows=2, cols=2, hp=300, vp=300, top=1.0, x0=0),
                          dict(rows=1, cols=2, hp=300, top=1.2, gap=1.5)],
                   bank_map={'1': dict(Nl=3, LG=1150, xb=600, yb=800, rc=1.0), '2': dict(direct_rho=1.6)},
                   positions=[dict(bank=1, row=1, col=1, type=0, load=None),
                              dict(bank=1, row=2, col=2, type=0, load=420),
                              dict(bank=2, row=1, col=1, type=1, load=250),
                              dict(bank=2, row=1, col=2, type=1)]),
         Lroute=1500, If_sc=25),
    dict(standard='BS', cables=[C630], installation='air', tg=40,
         air=dict(circuits=[dict(type=0, formation='flat_spaced', spacing=150),
                            dict(type=0, formation='trefoil')],
                  trough=dict(w=1.0, h=0.6), h_factor=0.9, solar=dict(sigma=0.5, H=900)),
         Lroute=500, If_sc=20),
    dict(standard='IEEE', cables=[C3SL], installation='duct',
         duct=dict(Do=160, Dd=140, soil_model='layers',
                   layers=[dict(X=0, Y=1.0, W=1.0, H=0.6, rho=1.0), dict(X=0, Y=0.4, W=1.2, H=0.3, rho=1.2)],
                   banks=[dict(rows=1, cols=3, hp=250, top=1.0)],
                   positions=[dict(bank=1, row=1, col=1, type=0), dict(bank=1, row=1, col=3, type=0)]),
         Lroute=1000, If_sc=31.5),
]


def _close_placed(o, a, tag):
    for k in ('x', 'y', 'T1', 'T2', 'T3', 'T4', 'R', 'lam1', 'lam2', 'Wd', 'I', 'theta_op', 'dt_int'):
        if o.get(k) is None and a.get(k) is None:
            continue
        same(o.get(k), a.get(k), f'{tag}.{k}')


@pytest.mark.parametrize('req', M4_CASES)
def test_mode4_matches_original(req):
    d = Driver()
    for fn in ('define_cable', 'solve_arrangement_xy', 'suite_adiabatic', 'calc_electrical', 'calc_induced',
               'emergency_rating'):
        d.spy(fn)
    d.run('mode4_main', mode4_answers(req))
    from app.engine import legacy_engine as L
    for i, cd in enumerate(req['cables']):
        cb, _ = mode4.build_cable(cd, L.STANDARDS[req['standard']])
        same(d.calls['define_cable'][i]['out'], cb, f'$cable{i}')
    placed_orig = d.calls['solve_arrangement_xy'][0]['args'][0]
    res = mode4.run_full_report(req)
    assert [p['tag'] for p in placed_orig] == [p['tag'] for p in res['placed']]
    for o, a in zip(placed_orig, res['placed']):
        _close_placed(o, a, o['tag'])
    ad_orig = [c['out'] for c in d.calls['suite_adiabatic']]
    for o, a in zip(ad_orig, res['reports']):
        same(o, a['short_circuit'], a['tag'] + '.sc')
    el_orig = [c['out'] for c in d.calls['calc_electrical']]
    for o, a in zip(el_orig, res['reports']):
        same(o, a['electrical'], a['tag'] + '.el')
    if req.get('emergency'):
        em_orig = [c['out'] for c in d.calls['emergency_rating']]
        for o, a in zip(em_orig, res['reports']):
            same(o, a['emergency'], a['tag'] + '.em')
