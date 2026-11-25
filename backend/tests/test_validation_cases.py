"""Original validation routines: they must run, every comparison line they
print must be captured by the dedicated parser, and the reported status must
match the numbers (no false PASS, no false FAIL). Expected statuses below are
the honest outcome of the source-provided benchmarks at this engine version -
if the engine changes, these tests force the documentation to change too."""
import re

import pytest

from app.validation.runner import CASES, run_case

EXPECTED = {
    'mode4_validate': ('PASS', 6, 0),
    'suite_validate': ('PASS', 9, 0),
    'emergency_validate': ('OUTSIDE_TOLERANCE', 6, 6),
    'mode4_cymcap_validate': ('PASS', 3, 0),
    'cymcap_ductbank_validate': ('PASS', 1, 2),
    'cymcap_3core_validate': ('KNOWN_GAPS', 0, 7),
    'volta_validate': ('OUTSIDE_TOLERANCE', 36, 0),
    'transco_validate': ('OUTSIDE_TOLERANCE', 4, 8),
    'soil_validate': ('PASS', 8, 16),
    'ground3c_validate': ('PASS', 4, 17),
    'ductbank_validate': ('OUTSIDE_TOLERANCE', 6, 6),
    'esf_validate': ('PASS', 4, 28),
}


@pytest.fixture(scope='module')
def results():
    return {c['id']: run_case(c['id']) for c in CASES}


def test_all_cases_listed():
    assert set(EXPECTED) == {c['id'] for c in CASES}


@pytest.mark.parametrize('cid', sorted(EXPECTED))
def test_case_status_and_row_counts(results, cid):
    r = results[cid]
    status, n_head, n_inter = EXPECTED[cid]
    assert r['error'] is None, r['error']
    heads = [x for x in r['rows'] if x['kind'] == 'headline']
    inters = [x for x in r['rows'] if x['kind'] == 'intermediate']
    assert (r['status'], len(heads), len(inters)) == (status, n_head, n_inter)


@pytest.mark.parametrize('cid', sorted(EXPECTED))
def test_status_consistent_with_rows(results, cid):
    r = results[cid]
    heads = [x for x in r['rows'] if x['kind'] == 'headline' and x['within'] is not None]
    if r['status'] == 'PASS':
        assert all(x['within'] for x in heads)
    if r['status'] == 'OUTSIDE_TOLERANCE':
        assert any(x['within'] is False for x in heads) or r['returned'] is False


def test_suite_lead_row_compares_final_values(results):
    lead = next(x for x in results['suite_validate']['rows'] if x['label'].startswith('lead'))
    assert lead['computed'] == lead['reference'] == 15.98


def test_every_dev_line_is_captured(results):
    """Any printed 'dev' figure in a line must appear in some parsed row."""
    for cid, r in results.items():
        devs_printed = len(re.findall(r'dev[ =]*[+-]?\d', r['output']))
        devs_parsed = sum(1 for x in r['rows'] if x.get('deviation') is not None)
        assert devs_parsed >= devs_printed, (cid, devs_printed, devs_parsed)
