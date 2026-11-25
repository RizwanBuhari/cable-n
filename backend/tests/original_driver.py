"""Loads the untouched ORIGINAL program as its own module and drives its
terminal dialogues with scripted answers, recording what its internal
functions return. Used by the parity tests to prove the web adapters produce
exactly what the original produces for the same answers."""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import os
import tempfile
from pathlib import Path

ORIGINAL = Path(__file__).resolve().parents[2] / 'reference' / 'original_engine' / 'cable_sizing_FINAL.py'


class UnexpectedPrompt(AssertionError):
    pass


def load_original():
    spec = importlib.util.spec_from_file_location('cable_sizing_original', ORIGINAL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Driver:
    def __init__(self):
        self.m = load_original()
        self.calls: dict[str, list] = {}
        self.prompts: list[str] = []

    def spy(self, name):
        orig = getattr(self.m, name)
        store = self.calls.setdefault(name, [])

        def wrapper(*a, **k):
            out = orig(*a, **k)
            store.append({'args': a, 'kwargs': k, 'out': copy.deepcopy(out)})
            return out
        setattr(self.m, name, wrapper)

    def run(self, entry: str, answers: list[str]) -> str:
        queue = [str(a) for a in answers]

        def fake_input(prompt=''):
            self.prompts.append(prompt)
            if not queue:
                raise UnexpectedPrompt(f'original asked an unscripted question: {prompt!r}')
            return queue.pop(0)
        self.m.input = fake_input
        buf = io.StringIO()
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp(prefix='cablen-orig-')
        os.chdir(tmp)  # anything the original writes lands in a temp dir
        try:
            with contextlib.redirect_stdout(buf):
                getattr(self.m, entry)()
        finally:
            os.chdir(cwd)
        out = buf.getvalue()
        if 'An unexpected error occurred' in out or 'Input Error' in out or 'Traceback' in out:
            raise AssertionError('original program reported an error:\n' + out[-3000:])
        if queue:
            raise AssertionError(f'{len(queue)} scripted answers were not consumed: {queue}; last prompts '
                                 f'{self.prompts[-3:]}')
        return out


# ------------------------------------------------------------ answer scripts
def mode1_answers(p: dict, arrangement_index: int | None) -> list[str]:
    a = [p['voltage'], p['voltage_drop_limit_pct'], p['power_factor'],
         '1' if p.get('insulation', 'xlpe') == 'xlpe' else '2',
         '1' if p['core_type'] == '1C' else '2', 'y' if p['armored'] else 'n',
         '1' if p['material'] == 'cu' else '2']
    if p['load_mode'] == 'current':
        a += ['1', p['current']]
    else:
        a += ['2', p['power'], p['power_unit']]
    a += ['1' if p['phase'] == 'single' else '2']
    if p['installation'] == 'buried':
        a += ['1', p['soil_resistivity'], p['soil_temp'], p['depth']]
    elif p['installation'] == 'duct':
        a += ['2', p['duct_resistivity'], p['soil_temp'], p['depth']]
    else:
        a += ['3', p['air_temp']]
    a += [p['cable_length']]
    if p.get('sc_check'):
        a += ['y', p['fault_kA'], p['fault_time'], '2' if p.get('fault_share') == 'full' else '1']
    else:
        a += ['n']
    if arrangement_index is not None:
        a += [str(arrangement_index)]
    a += ['n']  # no PDF
    return a


def mode2_answers(c: dict, feeders: list[dict], arrangement_index: int | None) -> list[str]:
    a = [c['voltage'], '1' if c['phase'] == 'single' else '2', c['voltage_drop_limit_pct'], c['power_factor'],
         '1' if c['core_type'] == '1C' else '2', 'y' if c['armored'] else 'n', '1' if c['material'] == 'cu' else '2']
    if c['installation'] == 'buried':
        a += ['1', c['soil_resistivity'], c['soil_temp'], c['depth']]
    elif c['installation'] == 'duct':
        a += ['2', c['duct_resistivity'], c['soil_temp'], c['depth']]
    else:
        a += ['3', c['air_temp']]
    a += (['y', c['fault_kA'], c['fault_time']] if c.get('sc_check') else ['n'])
    if arrangement_index is not None:
        a += [str(arrangement_index)]
    for i, f in enumerate(feeders):
        a += [f['tag']]
        if f.get('load_mode', 'current') == 'current':
            a += ['1', f['current']]
        else:
            a += ['2', f['power'], f['power_unit']]
        a += [f['cable_length'], '' if f.get('power_factor') is None else f['power_factor'],
              '' if f.get('voltage_drop_limit_pct') is None else f['voltage_drop_limit_pct']]
        a += ['y' if i < len(feeders) - 1 else 'n']
    a += ['n']  # no PDF
    return a


def mode3_answers(p: dict) -> list[str]:
    a = ['1' if p['installation'] == 'duct' else '2', len(p['banks']), p['soil_rho'], p['soil_temp']]
    if p.get('backfill_rho') is not None:
        a += ['y', p['backfill_rho'], {'worst': '1', 'native': '2', 'envelope': '3'}[p.get('rho_choice', 'worst')]]
    else:
        a += ['n']
    a += ['y' if p['armored'] else 'n', '1' if p['material'] == 'cu' else '2']
    for bi, b in enumerate(p['banks']):
        a += [b['rows'], b['cols'], b['h_pitch']]
        if b['rows'] > 1:
            a += [b['v_pitch']]
        a += [b['top_depth']]
        pos = {(q['row'], q['col']): q for q in b['positions']}
        for r in range(1, b['rows'] + 1):
            for c in range(1, b['cols'] + 1):
                q = pos.get((r, c))
                if q:
                    a += [q['desig'], '' if q.get('load') is None else q['load']]
                else:
                    a += ['']
        a += ['' if b.get('circuits') is None else b['circuits']]
        if bi < len(p['banks']) - 1:
            a += [p['gaps'][bi]]
    if len(p['banks']) > 1:
        a += ['' if p.get('interbank_override') is None else p['interbank_override']]
    a += ['n']  # no PDF
    return a


def _opt(v):
    return '' if v is None else v


def cable_answers(c: dict) -> list[str]:
    a = [c['desig'], '1' if c.get('mat', 'CU') == 'CU' else '2', c['U'], _opt(c.get('f')), _opt(c.get('theta')),
         c['dc'], _opt(c.get('tcs')), c['ti'], _opt(c.get('tis')), _opt(c.get('rho_ins')), _opt(c.get('t_wb'))]
    if c.get('t_wb'):
        a += [_opt(c.get('rho_wb'))]
    a += [{'stranded': '1', 'solid': '2', 'milliken': '3'}[c.get('conductor', 'stranded')]]
    a += [_opt(c.get('theta_scr'))]
    w = c.get('cu_wire')
    a += (['y', w['dw'], w['N']] if w else ['n'])
    t = c.get('cu_tape')
    a += (['y', _opt(t.get('tt')), _opt(t.get('wt')), 'y' if t.get('double') else 'n'] if t else ['n'])
    ld = c.get('lead')
    a += (['y', ld['tl']] if ld else ['n'])
    if c['desig'].startswith('3'):
        a += ['2' if c.get('n3_construction') == 'belted' else '1', _opt(c.get('D_laidup'))]
        if c.get('n3_construction') != 'belted':
            a += [_opt(c.get('rho_filler')), _opt(c.get('t2')), _opt(c.get('G_T2')), _opt(c.get('lay_length'))]
    a += [_opt(c.get('t_bed')), _opt(c.get('rho_bed'))]
    ar = c.get('armour')
    if ar:
        a += ['y', ar['type']]
        if ar['type'] in ('AWA', 'SWA'):
            a += [ar['da'], ar['Na']]
        else:
            a += [ar['th'], 'y' if ar.get('double') else 'n']
        a += [_opt(ar.get('R20'))]
    else:
        a += ['n']
    a += [c['tj'], _opt(c.get('rho_j')), _opt(c.get('De'))]
    ins = (c.get('insulation') or 'XLPE').upper()
    a += [{'XLPE': '1', 'EPR': '2', 'PILC': '3', 'PVC': '4'}.get(ins, '5')]
    if ins not in ('XLPE', 'EPR', 'PILC', 'PVC'):
        a += [_opt(c.get('eps')), _opt(c.get('tan_delta'))]
    a += ['1' if c.get('bonding') == 'single' else '2']
    return a


def mode4_answers(req: dict) -> list[str]:
    std_idx = {'IEC': '1', 'BS': '2', 'IEEE': '3', 'IS': '4'}[req.get('standard', 'IEC')]
    a = ['', std_idx] + cable_answers(req['cables'][0])
    for extra in req['cables'][1:]:
        a += ['y'] + cable_answers(extra)
    a += ['n']
    inst = req['installation']
    a += [{'buried': '1', 'duct': '2', 'air': '3'}[inst], _opt(req.get('tg'))]
    fm_idx = {'trefoil': '1', 'flat_touching': '2', 'flat_spaced': '3'}
    if inst == 'air':
        ai = req.get('air') or {}
        for circ in ai['circuits']:
            a += [str(circ['type'] + 1)]
            if req['cables'][circ['type']]['desig'].startswith('1'):
                a += [fm_idx[circ.get('formation', 'trefoil')]]
                if circ.get('formation') == 'flat_spaced':
                    a += [circ['spacing']]
        a += ['']
        d = ai.get('ducts')
        if d:
            a += ['y', d['Do'], d['Dd'], _opt(d.get('rho_d')), _opt(d.get('n_in_duct')),
                  '2' if d.get('filled') else '1']
            if d.get('filled'):
                a += [_opt(d.get('rho_fill'))]
            a += [_opt(d.get('thm'))]
        else:
            a += ['n']
        tr = ai.get('trough')
        a += (['y', tr['w'], tr['h']] if tr else ['n'])
        a += [_opt(ai.get('h_factor'))]
        so = ai.get('solar')
        a += (['y', _opt(so.get('sigma')), _opt(so.get('H'))] if so else ['n'])
    elif inst == 'duct':
        dq = req['duct']
        a += [_opt(dq.get('rho_e')), len(dq['banks'])]
        for i, b in enumerate(dq['banks']):
            a += [b['rows'], b['cols'], b['hp']]
            if b['rows'] > 1:
                a += [b['vp']]
            a += [b['top']]
            a += [_opt(b.get('x0'))] if i == 0 else [b['gap']]
        if len(dq['banks']) > 1:
            a += [_opt(dq.get('rho_native'))]
        a += [dq['Do'], dq['Dd'], _opt(dq.get('rho_d')), _opt(dq.get('thm'))]
        fill = dq.get('fill', 'air')
        a += [{'air': '1', 'filled': '2', 'zero': '3'}[fill]]
        if fill == 'filled':
            a += [_opt(dq.get('rho_fill'))]
        model = dq.get('soil_model', 'none')
        if model == 'layers':
            a += ['1']
            for i, ly in enumerate(dq['layers']):
                a += [f'L{i+1}', ly['X'], ly['Y'], ly['W'], ly['H'], ly['rho']]
            a += ['']
        else:
            a += ['2']
            if model == 'bank':
                a += ['y']
                for b in range(1, len(dq['banks']) + 1):
                    e = dq['bank_map'][str(b)]
                    if e.get('direct_rho') is not None:
                        a += [e['direct_rho']]
                    else:
                        a += ['', e['Nl'], e['LG'], e['xb'], e['yb'], e['rc']]
            else:
                a += ['n']
        n_in = dq.get('n_in_duct', 3)
        a += [str(n_in)]
        loads = any(q.get('load') is not None for q in dq['positions'])
        a += ['y' if loads else '']
        pos = {(q['bank'], q['row'], q['col']): q for q in dq['positions']}
        for bi, b in enumerate(dq['banks'], 1):
            for r in range(1, b['rows'] + 1):
                for c in range(1, b['cols'] + 1):
                    q = pos.get((bi, r, c))
                    if q:
                        a += [str(q['type'] + 1)]
                        if loads:
                            a += [_opt(q.get('load'))]
                    else:
                        a += ['']
    else:
        bq = req['buried']
        a += [_opt(bq.get('rho_e')), bq['L']]
        if bq.get('trough_rho') is not None:
            a += ['y', bq['trough_rho']]
        else:
            a += ['n']
            a += (['y', bq['backfill_rho']] if bq.get('backfill_rho') is not None else ['n'])
        for circ in bq['circuits']:
            a += [str(circ['type'] + 1), circ['x']]
            if req['cables'][circ['type']]['desig'].startswith('1'):
                a += [fm_idx[circ.get('formation', 'trefoil')]]
                if circ.get('formation') == 'flat_spaced':
                    a += [circ['spacing']]
        a += ['']
    a += [req.get('Lroute', 1000), _opt(req.get('rho_earth')), _opt(req.get('t_sc')), req.get('If_sc', 31.5)]
    if inst == 'buried':
        a += ['y' if req.get('emergency') else 'n']
        if req.get('emergency'):
            a += [_opt(req.get('theta_em'))]
    a += ['n']  # no PDF
    return a
