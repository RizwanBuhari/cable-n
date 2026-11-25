"""Public, stateless API: no login, nothing stored, abuse limits enforced."""
import io
import time

import pytest
from openpyxl import Workbook
from pypdf import PdfReader

V = '/api/v1'
M1 = dict(voltage=415, voltage_drop_limit_pct=5, power_factor=0.85, phase='three', load_mode='current', current=250,
          insulation='xlpe', core_type='3C', armored=True, material='cu', installation='buried', soil_resistivity=1.5,
          soil_temp=30, depth=0.8, cable_length=150, sc_check=True, fault_kA=25, fault_time=1, fault_share='equal')
M3 = dict(installation='duct', soil_rho=1.5, soil_temp=35, armored=True, material='cu',
          banks=[dict(rows=1, cols=2, h_pitch=250, top_depth=1.0,
                      positions=[dict(row=1, col=1, desig='3x240', load=300)])])
C630 = {'desig': '1x630', 'mat': 'CU', 'U': 33, 'dc': 30.05, 'ti': 8.0, 'tj': 3.0,
        'cu_tape': {'tt': 0.076, 'wt': 50}, 'armour': {'type': 'AWA', 'da': 2.5, 'Na': 60}}
M4 = dict(standard='IEC', cables=[C630], installation='buried',
          buried=dict(rho_e=1.2, L=1000, circuits=[dict(type=0, x=0, formation='trefoil')]), Lroute=1000, If_sc=31.5)
BATCH = dict(common=dict(voltage=415, phase='three', voltage_drop_limit_pct=5, power_factor=0.85, core_type='3C',
                         armored=True, material='cu', installation='air', air_temp=40, sc_check=False),
             feeders=[dict(tag='F1', current=100, cable_length=100), dict(tag='F2', current=-1, cable_length=50),
                      dict(tag='F3', load_mode='power', power=75, power_unit='KW', cable_length=200)])
MODES = [('single-feeder', M1), ('batch', BATCH), ('current-rating', M3), ('advanced-mvhv', M4)]


def test_health(client):
    r = client.get(f'{V}/health').json()
    assert r['status'] == 'ok' and r['engine_ok']


@pytest.mark.parametrize('slug,inputs', MODES)
def test_every_mode_runs_without_login(client, slug, inputs):
    r = client.post(f'{V}/calculations/{slug}', json={'inputs': inputs})
    assert r.status_code == 200, r.text
    assert r.json()['result']['verification_notice']


def test_no_account_endpoints(client):
    for path in ('/auth/login', '/users', '/projects'):
        assert client.post(f'{V}{path}', json={}).status_code in (404, 405)


def test_validation_errors_are_422(client):
    r = client.post(f'{V}/calculations/single-feeder', json={'inputs': dict(M1, voltage=-1)})
    assert r.status_code == 422 and r.json()['detail']['errors']
    r = client.post(f'{V}/calculations/single-feeder', json={'inputs': dict(M1, power_factor=0, load_mode='power',
                                                                             power=5, power_unit='KW')})
    assert r.status_code == 422


def test_body_size_limit(client):
    big = {'inputs': dict(M1, pad='x' * 600_000)}
    assert client.post(f'{V}/calculations/single-feeder', json=big).status_code == 413


def test_batch_size_cap(client):
    feeders = [dict(tag=f'F{i}', current=10, cable_length=10) for i in range(201)]
    r = client.post(f'{V}/calculations/batch', json={'inputs': dict(BATCH, feeders=feeders)})
    assert r.status_code == 422


def test_rate_limit(client, monkeypatch):
    from app.core import protect
    from app.core.config import get_settings
    protect.reset_for_tests()
    monkeypatch.setattr(get_settings(), 'CALC_RATE_PER_MINUTE', 3)
    codes = [client.post(f'{V}/calculations/single-feeder', json={'inputs': M1}).status_code for _ in range(5)]
    assert codes[:3] == [200] * 3 and codes[3] == 429
    protect.reset_for_tests()


@pytest.mark.parametrize('slug,inputs', MODES)
def test_pdf_report_recomputed_and_traceable(client, slug, inputs):
    meta = {'title': 'Test feeder', 'project_name': 'Demo', 'prepared_by': 'A. Engineer', 'report_number': 'T-1'}
    r = client.post(f'{V}/outputs/report.pdf', json={'mode': slug, 'inputs': inputs, 'meta': meta,
                                                      'kind': 'detailed'})
    assert r.status_code == 200, r.text
    assert r.content[:4] == b'%PDF' and len(r.headers['x-input-hash']) == 64
    text = ''.join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages[:3])
    assert 'T-1' in text and 'NOT REVIEWED' in text and 'Elsewedy' not in text


@pytest.mark.parametrize('ext', ['xlsx', 'csv'])
@pytest.mark.parametrize('slug,inputs', MODES)
def test_exports(client, ext, slug, inputs):
    r = client.post(f'{V}/outputs/export.{ext}', json={'mode': slug, 'inputs': inputs})
    assert r.status_code == 200


def test_report_temp_files_removed(client):
    import tempfile
    from pathlib import Path
    before = set(Path(tempfile.gettempdir()).glob('cablen-rpt-*'))
    client.post(f'{V}/outputs/report.pdf', json={'mode': 'single-feeder', 'inputs': M1})
    assert set(Path(tempfile.gettempdir()).glob('cablen-rpt-*')) == before


def test_batch_job_progress_and_cancel(client):
    jid = client.post(f'{V}/calculations/batch/jobs', json={'inputs': BATCH}).json()['job_id']
    for _ in range(200):
        j = client.get(f'{V}/jobs/{jid}').json()
        if j['status'] in ('completed', 'failed'):
            break
        time.sleep(0.05)
    assert j['status'] == 'completed' and j['done'] == j['total'] == 3
    assert j['result']['result']['summary']['invalid'] == 1
    assert client.get(f'{V}/jobs/doesnotexist').status_code == 404


def test_batch_template_roundtrip_and_bad_values(client):
    tpl = client.get(f'{V}/calculations/batch/template.xlsx')
    r = client.post(f'{V}/calculations/batch/import', files={'file': ('f.xlsx', tpl.content, 'application/x')})
    assert r.status_code == 200 and r.json()['feeders'][0]['tag'] == 'F-01'
    wb = Workbook(); ws = wb.active; ws.title = 'Feeders'
    ws.append(['Feeder tag', 'Load mode (current/power)', 'Load current (A)', 'Route length (m)'])
    ws.append(['A', 'current', 'abc', 100])
    buf = io.BytesIO(); wb.save(buf)
    r = client.post(f'{V}/calculations/batch/import', files={'file': ('f.xlsx', buf.getvalue(), 'application/x')})
    assert any('not a number' in p for p in r.json()['problems'])
    r = client.post(f'{V}/calculations/batch/import', files={'file': ('f.xlsx', b'not a zip', 'application/x')})
    assert r.status_code == 400


def test_sensitivity_points_are_engine_results(client):
    r = client.post(f'{V}/calculations/sensitivity', json={'mode': 'single_feeder', 'inputs': M1,
                                                            'variable': 'soil_resistivity', 'values': [1.0, 2.0, 4.0]})
    pts = r.json()['points']
    assert len(pts) == 3 and pts[2].get('outside_supported_range') and r.json()['warnings']
    assert pts[0]['derated_current'] >= pts[1]['derated_current']
    r = client.post(f'{V}/calculations/sensitivity', json={'mode': 'single_feeder', 'inputs': M1,
                                                            'variable': 'depth', 'values': list(range(1, 30))})
    assert r.status_code == 422


def test_mode4_helpers(client):
    assert client.post(f'{V}/calculations/advanced-mvhv/cable-preview', json={'cable': C630}).json()['T1'] > 0
    assert client.post(f'{V}/calculations/advanced-mvhv/sensitivity', json={'inputs': M4}).json()['depth']
    assert client.post(f'{V}/calculations/advanced-mvhv/isotherms', json={'inputs': M4}).json()['available']


def test_cost_estimate(client):
    r = client.post(f'{V}/calculations/cost-estimate', json={'currency': 'USD', 'lines': [
        dict(label='A', size='185', runs=2, length_m=100, cost_per_m=10, install_cost=500, load_current_A=300,
             loss_load_factor=0.5, tariff_per_kwh=0.1, years=10)]})
    line = r.json()['lines'][0]
    assert line['capex'] == 2 * 100 * 10 + 500 and line['annual_loss_kWh'] > 0


def test_library_and_validation(client):
    lib = client.get(f'{V}/cable-library').json()
    assert len(lib['records']) > 50
    cases = client.get(f'{V}/validation/cases').json()
    assert len(cases['cases']) == 12 and 'not certification' in cases['disclaimer']
    jid = client.post(f'{V}/validation/run', json={'case_ids': ['mode4_validate']}).json()['job_id']
    for _ in range(200):
        j = client.get(f'{V}/jobs/{jid}').json()
        if j['status'] == 'completed':
            break
        time.sleep(0.05)
    assert j['result']['results'][0]['status'] == 'PASS'


def test_datasheet_extraction_rejects_non_pdf(client):
    r = client.post(f'{V}/cable-library/extract-datasheet', files={'file': ('a.pdf', b'hello', 'application/pdf')})
    assert r.status_code == 400


def test_assistant_disabled_gracefully(client):
    assert client.get(f'{V}/assistant/status').json()['configured'] is False
    r = client.post(f'{V}/assistant/chat', json={'message': 'hi'})
    assert r.status_code == 503


def test_premium_key(client):
    from app.api.reference import sign_key
    good = sign_key({'v': 1, 'label': 'x'}, 'test-premium-secret')
    assert client.post(f'{V}/premium/verify', json={'key': good}).json()['ad_free'] is True
    assert client.post(f'{V}/premium/verify', json={'key': good[:-2] + 'zz'}).status_code == 400
    expired = sign_key({'v': 1, 'exp': '2001-01-01'}, 'test-premium-secret')
    assert client.post(f'{V}/premium/verify', json={'key': expired}).status_code == 400


def test_path_traversal_blocked(client):
    r = client.get('/..%2f..%2fbackend%2f.env')
    assert r.status_code in (404, 200) and b'SECRET' not in r.content
