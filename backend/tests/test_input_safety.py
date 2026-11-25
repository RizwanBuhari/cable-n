"""Unsafe or invalid inputs must be blocked, never turned into results."""
import math

import pytest
from pydantic import ValidationError

from app.engine import mode1, mode3, mode4
from app.engine.mode1 import InputRejected
from app.engine.runtime import find_non_finite
from app.services.calculations import compute, validate_inputs

BASE = dict(voltage=415, voltage_drop_limit_pct=5, power_factor=0.85, phase='three', load_mode='current', current=100,
            insulation='xlpe', core_type='3C', armored=True, material='cu', installation='buried', soil_resistivity=1.5,
            soil_temp=30, depth=0.8, cable_length=100, sc_check=False)


def run(**kw):
    return compute('single_feeder', validate_inputs('single_feeder', dict(BASE, **kw)))


@pytest.mark.parametrize('kw', [
    dict(voltage=0), dict(voltage=-400), dict(current=-5), dict(current=0), dict(cable_length=0),
    dict(power_factor=1.2), dict(power_factor=-0.1), dict(voltage_drop_limit_pct=150), dict(depth=5),
    dict(soil_temp=120), dict(voltage=float('nan')), dict(current=float('inf')),
    dict(load_mode='power', current=None), dict(installation='duct'),
    dict(sc_check=True), dict(fault_time=9, sc_check=True, fault_kA=10),
    dict(power_unit='HP', load_mode='power', power=5), dict(unknown_field=1),
])
def test_invalid_rejected(kw):
    with pytest.raises((ValidationError, InputRejected)):
        run(**kw)


def test_zero_power_factor_with_kw_rejected():
    with pytest.raises(InputRejected, match='Power factor'):
        run(load_mode='power', power=50, power_unit='KW', power_factor=0, current=None)


def test_zero_power_factor_with_kva_allowed():
    """kVA does not divide by PF in the original, so PF 0 is a valid (if odd) input there."""
    r = run(load_mode='power', power=50, power_unit='KVA', power_factor=0, current=None)
    assert math.isclose(r['design_current'], 50000 / (415 * math.sqrt(3)))


def test_ambient_at_conductor_limit_blocked():
    with pytest.raises(InputRejected, match='Ca = 0.01'):
        run(installation='air', air_temp=90, soil_resistivity=None, soil_temp=None, depth=None)
    with pytest.raises(InputRejected):
        run(installation='air', air_temp=75, insulation='pvc', soil_resistivity=None, soil_temp=None, depth=None)


@pytest.mark.parametrize('unit,factor', [('KW', 1e3), ('KVA', 1e3), ('MW', 1e6), ('MVA', 1e6)])
@pytest.mark.parametrize('phase', ['single', 'three'])
def test_power_unit_conversion(unit, factor, phase):
    r = run(load_mode='power', power=2, power_unit=unit, phase=phase, current=None)
    pf = 0.85 if unit in ('KW', 'MW') else 1.0
    k = math.sqrt(3) if phase == 'three' else 1.0
    assert math.isclose(r['design_current'], 2 * factor / (415 * pf * k), rel_tol=1e-12)


def test_percent_vs_fraction():
    r = run(voltage_drop_limit_pct=4)
    assert r['legacy_inputs']['voltage_drop_limit'] == 0.04


def test_out_of_table_warnings_disclosed():
    r = run(soil_resistivity=5.0, depth=0.3)
    ws = ' '.join(r['warnings'])
    assert 'outside the rating-factor table' in ws and 'outside the depth-factor table' in ws


def test_pvc_approximation_disclosed():
    r = run(insulation='pvc')
    assert any('PVC' in w and 'approximation' in w for w in r['warnings'])


def test_parallel_short_circuit_assumption_disclosed():
    r = run(current=900, sc_check=True, fault_kA=40, fault_time=1, fault_share='equal')
    assert any('shares equally' in w for w in r['warnings'])


def test_unrated_arrangement_rejected():
    with pytest.raises(InputRejected):
        run(arrangement='Airflat')


def test_results_are_finite():
    r = run(current=2500, cable_length=800)
    assert find_non_finite(r) == []


def test_mode3_bad_designation_and_size():
    p = dict(installation='duct', soil_rho=1.5, soil_temp=35, armored=True, material='cu',
             banks=[dict(rows=1, cols=1, h_pitch=250, top_depth=1.0, positions=[dict(row=1, col=1, desig='2x240')])])
    with pytest.raises(InputRejected, match='designation'):
        mode3.run_rating(p)
    p['banks'][0]['positions'][0]['desig'] = '3x7'
    with pytest.raises(InputRejected, match='not in the'):
        mode3.run_rating(p)
    p['banks'][0]['positions'] = []
    with pytest.raises(InputRejected, match='No cables'):
        mode3.run_rating(p)


def test_mode4_overlap_and_ranges_rejected():
    c = mode4.PRESETS['mv_33kv_1x630_awa']['cable']
    req = dict(standard='IEC', cables=[c], installation='buried',
               buried=dict(rho_e=1.2, L=1000, circuits=[dict(type=0, x=0), dict(type=0, x=50)]),
               Lroute=1000, If_sc=31.5)
    with pytest.raises(InputRejected, match='overlap'):
        mode4.run_full_report(req)
    bad = dict(c, ti=100)
    with pytest.raises(InputRejected, match='insulation thickness'):
        mode4.build_cable(bad)
    with pytest.raises(InputRejected, match='IEC 60228'):
        mode4.build_cable(dict(c, desig='1x333'))
    req2 = dict(req, tg=75, cables=[dict(c, theta=70)],
                buried=dict(rho_e=1.2, L=1000, circuits=[dict(type=0, x=0)]))
    with pytest.raises(InputRejected, match='at/above'):
        mode4.run_full_report(req2)


def test_arrangement_options_api_shape():
    opts = mode1.options_for(dict(material='cu', armored=False, core_type='1C', installation='air'))
    assert opts and all('sizes' in o and o['sizes'] for o in opts)
