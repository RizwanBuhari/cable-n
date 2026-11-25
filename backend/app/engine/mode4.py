"""Mode 4 - full IEC 60287 / 60949 MV-HV analysis.

The original collects everything through two terminal dialogues:
define_cable() and mode4_full_report(). Neither can run on a server, so this
module contains their NON-INTERACTIVE equivalents:

* build_cable()      - line-for-line transcription of define_cable(): the same
                       derived diameters, metallic layers (make_layer), 3-core
                       lay-up, Fig.6 G factor, armour, dielectric table,
                       equivalent screen resistance and bonding;
* run_full_report()  - transcription of mode4_full_report(): the same
                       placement (_expand_circuit / bank coordinates), the same
                       call to solve_arrangement_xy(), and the same per-cable
                       calc_electrical / calc_sequence / calc_induced /
                       suite_adiabatic / emergency_rating calls.

No formula lives here - every number comes from legacy_engine. Parity tests in
tests/test_mode4_parity.py drive the ORIGINAL dialogues with scripted answers
and compare the result with these builders.
"""
from __future__ import annotations

import copy
import math
import re

from . import legacy_engine as L
from .mode1 import InputRejected
from .runtime import run_engine, to_jsonable, find_non_finite, ENGINE_VERSION, latin1

DESIG_RE = re.compile(r'^([13])\s*x\s*(\d+)$')
CONDUCTOR_KSKP = {'stranded': (1.0, 0.8), 'solid': (1.0, 1.0), 'milliken': (0.435, 0.37)}
INSULATION_TABLE = {'XLPE': (2.5, 0.0004), 'EPR': (3.0, 0.003), 'PILC': (4.0, 0.01), 'PVC': (8.0, 0.1)}


def _rng(name, v, lo, hi):
    """Same bounds the original prompts enforce (get_valid_float limits)."""
    v = float(v)
    if not math.isfinite(v) or v < lo or v > hi:
        raise InputRejected(f'{name} must be between {lo} and {hi} (got {v}).')
    return v


def _opt(d, key, default, lo, hi, name=None):
    v = d.get(key)
    if v is None or v == '':
        return float(default)
    return _rng(name or key, v, lo, hi)


# ------------------------------------------------------------ cable builder
def build_cable(d: dict, std: dict | None = None) -> tuple[dict, dict]:
    """Returns (cb, info). cb is exactly what define_cable() returns for the
    same answers; info carries the previews define_cable() prints."""
    info = {}
    cb = {}
    m = DESIG_RE.match(str(d['desig']).strip().lower())
    if not m:
        raise InputRejected('Designation must be 1x<size> or 3x<size> (e.g. 1x400, 3x150).')
    cb['n'] = 1 if m.group(1) == '1' else 3
    cb['size'] = int(m.group(2))
    cb['desig'] = f"{m.group(1)}x{cb['size']}"
    cb['mat'] = 'CU' if str(d.get('mat', 'CU')).upper() == 'CU' else 'AL'
    if cb['size'] not in L.IEC_R0_20C[cb['mat']]:
        raise InputRejected(f"size {cb['size']} not in IEC 60228 table for {cb['mat']}: "
                            f"{sorted(L.IEC_R0_20C[cb['mat']])}")
    cb['U'] = _rng('Rated voltage U', d['U'], 1, 500)
    cb['U0'] = cb['U'] / math.sqrt(3)
    f_def = std['f'] if std else 50.0
    cb['f'] = _opt(d, 'f', f_def, 16, 400, 'Frequency')
    cb['theta'] = _opt(d, 'theta', 90.0, 50, 250, 'Max conductor temperature')

    cb['dc'] = _rng('dc conductor diameter', d['dc'], 4, 80)
    cb['tcs'] = _opt(d, 'tcs', 0.7, 0, 4, 'conductor screen thickness')
    cb['ti'] = _rng('insulation thickness', d['ti'], 2, 40)
    cb['tis'] = _opt(d, 'tis', 0.7, 0, 4, 'insulation screen thickness')
    cb['rho_ins'] = _opt(d, 'rho_ins', 3.5, 1, 10, 'insulation rho')
    cb['Dcs'] = cb['dc'] + 2 * cb['tcs']
    cb['Di'] = cb['Dcs'] + 2 * cb['ti']
    cb['Dis'] = cb['Di'] + 2 * cb['tis']
    cb['T1_extra'] = 0.0
    t_wb = _opt(d, 't_wb', 0.0, 0, 3, 'water-blocking tape thickness')
    if t_wb > 0:
        rho_wb = _opt(d, 'rho_wb', 12.0, 1, 20, 'tape rho')
        cb['t_wb'], cb['rho_wb'] = t_wb, rho_wb
        cb['T1_extra'] = ((rho_wb - cb['rho_ins']) / (2 * math.pi)) * \
            math.log((cb['dc'] + 2 * t_wb) / cb['dc'])
    cb['ks'], cb['kp'] = CONDUCTOR_KSKP.get(d.get('conductor') or 'stranded', (1.0, 0.8))

    cb['theta_scr'] = _opt(d, 'theta_scr', 85.0, 40, 120, 'Screen operating temperature')
    layers = []
    d_run = cb['Dis']
    w = d.get('cu_wire')
    if w:
        dw = _rng('screen wire diameter', w['dw'], 0.3, 4)
        Nw = int(_rng('number of screen wires', w['N'], 6, 200))
        aw = math.pi * dw ** 2 / 4
        layers.append(L.make_layer('Cu wire screen', 'copper', Nw * aw, d_run + dw, dw, 'wires', aw))
        d_run += 2 * dw
    t = d.get('cu_tape')
    if t:
        tt = _opt(t, 'tt', 0.15, 0.05, 1, 'tape thickness')
        wt = _opt(t, 'wt', 15.0, 5, 60, 'tape width')
        dbl = 2 if t.get('double') else 1
        layers.append(L.make_layer('Cu tape', 'copper', tt * wt * dbl, d_run + tt, tt, 'tape', tt * wt))
        d_run += 2 * tt
    ld = d.get('lead')
    if ld:
        tl = _rng('lead sheath thickness', ld['tl'], 0.8, 6)
        layers.append(L.make_layer('Lead sheath', 'lead', math.pi * tl * (d_run + tl),
                                   d_run + tl, tl, 'lead', 0))
        d_run += 2 * tl
    if not layers:
        info['warning_no_screen'] = 'No metallic screen defined - MV cables normally require one.'
    cb['screen_layers'] = layers
    cb['D_over_screen'] = d_run
    kinds = [L.layer_get(l, 'kind') for l in layers]
    cb['screen'] = ('wires' if 'wires' in kinds else 'tape' if 'tape' in kinds else
                    'lead' if 'lead' in kinds else None)

    if cb['n'] == 3:
        cb['n3_construction'] = 'belted' if d.get('n3_construction') == 'belted' else 'screened'
        D_assembly = d_run * (1 + 2 / math.sqrt(3))
        info['D_assembly'] = D_assembly
        ov = d.get('D_laidup')
        cb['D_laidup'] = float(ov) if ov not in (None, '') else D_assembly
        d_run = cb['D_laidup']
        cb['D_over_screen'] = d_run
        d_over_core = D_assembly / (1 + 2 / math.sqrt(3))
        if cb['n3_construction'] == 'screened':
            cb['rho_filler'] = _opt(d, 'rho_filler', 5.0, 1, 10, 'filler rho')
            _t2 = _opt(d, 't2', 1.0, 0.1, 30, 'thickness between core screens and armour')
            _g = L.iec_G_fig6(_t2, d_over_core)
            info['G_fig6'] = _g
            info['t_over_d'] = _t2 / d_over_core
            gv = d.get('G_T2')
            cb['G_T2'] = float(gv) if gv not in (None, '') else _g
            info['T2_SL'] = cb['rho_filler'] * cb['G_T2'] / (6 * math.pi)
            if X_ok := (0.045 <= info['t_over_d'] <= 0.06):
                pass
            info['G_extrapolated'] = not X_ok
            _ll = _opt(d, 'lay_length', 0.0, 0, 3000, 'core lay length')
            if _ll:
                cb['lay_length'] = _ll
                info['C_LL'] = L.core_lay_factor(cb)

    cb['t_bed'] = _opt(d, 't_bed', 1.0, 0, 20, 'bedding thickness')
    cb['rho_bed'] = _opt(d, 'rho_bed', 3.5, 1, 10, 'bedding rho')
    d_run += 2 * cb['t_bed']

    cb['armour'] = None
    a = d.get('armour')
    if a:
        at = str(a['type']).upper()
        if at not in L.ARMOUR_MAT:
            raise InputRejected('Armour type must be AWA, SWA, STA or ATA.')
        if at in ('AWA', 'SWA'):
            da = _rng('armour wire diameter', a['da'], 0.8, 6)
            Na = int(_rng('number of armour wires', a['Na'], 10, 200))
            area = Na * math.pi * da ** 2 / 4
            th = da
        else:
            th = _rng('armour tape thickness', a['th'], 0.1, 2)
            area = math.pi * th * (d_run + th) * (2 if a.get('double') else 1)
        cb['armour'] = {'type': at, 'mat': L.ARMOUR_MAT[at], 'area': area,
                        'dmean': d_run + th, 'th': th,
                        'kind': 'wires' if at in ('AWA', 'SWA') else 'tape',
                        'unit_area': (math.pi * th ** 2 / 4) if at in ('AWA', 'SWA') else area}
        r20 = a.get('R20')
        if r20 not in (None, ''):
            cb['armour']['R20'] = float(r20)
            _al = 0.0045 if L.ARMOUR_MAT[at] == 'steel' else 0.00403
            cb['armour']['R_hot'] = float(r20) * (1 + _al * (cb.get('theta_scr', 85.0) - 20))
        d_run += 2 * th

    cb['tj'] = _rng('Outer jacket thickness', d['tj'], 1, 15)
    cb['rho_j'] = _opt(d, 'rho_j', 3.5, 1, 10, 'jacket rho')
    info['De_computed'] = d_run + 2 * cb['tj']
    cb['De'] = _opt(d, 'De', d_run + 2 * cb['tj'], 10, 300, 'Overall diameter De')

    ins = (d.get('insulation') or 'XLPE').upper()
    if ins in INSULATION_TABLE:
        cb['eps'], cb['tan_delta'] = INSULATION_TABLE[ins]
    else:
        cb['eps'] = _opt(d, 'eps', 2.5, 1.5, 10, 'relative permittivity')
        cb['tan_delta'] = _opt(d, 'tan_delta', 0.001, 0, 0.2, 'tan delta')
    info['insulation'] = ins
    info['Wd_preview'] = L.iec_dielectric_Wd(cb['U0'], cb['Di'], cb['Dcs'], cb['f'],
                                             eps=cb['eps'], tan_delta=cb['tan_delta'])

    cond_tot = 0.0
    for lyr in layers:
        matl = L.layer_get(lyr, 'matl'); A = L.layer_get(lyr, 'A'); kind = L.layer_get(lyr, 'kind')
        R20 = L.ADIA_RHO20[matl] / A * (1.05 if kind == 'wires' else 1.0)
        beta = L.ADIA_K[matl][1]
        Rhot = R20 * (beta + cb['theta_scr']) / (beta + 20)
        cond_tot += 1 / Rhot
    cb['Rs_hot'] = 1 / cond_tot if cond_tot else 1e9
    if layers:
        cb['d_scr_mean'] = sum(L.layer_get(l, 'dm') for l in layers) / len(layers)
        cb['t_scr'] = sum(L.layer_get(l, 'th') for l in layers)
        cb['Ds_out'] = cb['D_over_screen']
    cb['bonding'] = 'single' if d.get('bonding') == 'single' else 'both_ends'
    if cb['De'] < info['De_computed'] - 1e-9:
        info['warning_De'] = (f"Overall diameter De {cb['De']:.2f} mm is smaller than the "
                              f"build-up {info['De_computed']:.2f} mm.")
    return cb, info


def describe_cable(cb: dict, info: dict | None = None) -> dict:
    """Derived geometry and thermal resistances for display."""
    c = copy.deepcopy(cb)
    T1, T2, T3, note = L.cable_thermal(c)
    out = {k: cb.get(k) for k in ('desig', 'n', 'size', 'mat', 'U', 'U0', 'f', 'theta', 'dc', 'Dcs',
                                   'Di', 'Dis', 'D_over_screen', 'D_laidup', 'De', 'tj', 'Rs_hot',
                                   'd_scr_mean', 't_scr', 'eps', 'tan_delta', 'bonding', 'ks', 'kp',
                                   'n3_construction', 'G_T2', 'T1_extra', 'theta_scr')}
    out['screen_layers'] = [dict(l) for l in cb['screen_layers']]
    out['armour'] = cb.get('armour')
    out['T1'], out['T2'], out['T3'] = T1, T2, T3
    out['thermal_note'] = note
    out['C_LL'] = L.core_lay_factor(cb)
    out['info'] = info or {}
    return to_jsonable(out)


# ------------------------------------------------------------ full report
def _bank_coords(banks_in: list[dict]) -> list[dict]:
    """Same coordinate construction as collect_duct_banks()."""
    banks = []
    x_cursor = 0.0
    for b, bi in enumerate(banks_in, 1):
        rows = int(_rng(f'Bank {b} rows', bi['rows'], 1, 8))
        cols = int(_rng(f'Bank {b} columns', bi['cols'], 1, 12))
        hp = _rng(f'Bank {b} horizontal pitch', bi['hp'], 40, 3000)
        vp = _rng(f'Bank {b} vertical pitch', bi['vp'], 40, 3000) if rows > 1 else 0.0
        top = _rng(f'Bank {b} depth to top row', bi['top'], 0.2, 8) * 1000
        if b == 1:
            x0 = _opt(bi, 'x0', 0.0, -20000, 20000, 'x of bank-1 left column')
        else:
            gap = _rng(f'gap from bank {b-1} to bank {b}', bi['gap'], 0.05, 30) * 1000
            x0 = x_cursor + gap
        coords = {}
        for r in range(1, rows + 1):
            for c in range(1, cols + 1):
                coords[(r, c)] = (x0 + (c - 1) * hp, top + (r - 1) * vp)
        banks.append(dict(id=b, rows=rows, cols=cols, hp=hp, vp=vp, top=top, x0=x0, coords=coords))
        x_cursor = x0 + (cols - 1) * hp
    return banks


def prepare_arrangement(req: dict):
    """Builds types/placed and the solver arguments, as mode4_full_report()."""
    std_key = req.get('standard') or 'IEC'
    if std_key not in L.STANDARDS:
        raise InputRejected('Unknown standard.')
    std = L.STANDARDS[std_key]
    if not req.get('cables'):
        raise InputRejected('Define at least one cable type.')
    types, infos = [], []
    for cd in req['cables']:
        cb, info = build_cable(cd, std)
        types.append(cb); infos.append(info)

    inst_name = req['installation']
    inst = {'buried': '1', 'duct': '2', 'air': '3'}[inst_name]
    tg_def = std['tg_air'] if inst == '3' else std['tg_ground']
    tg = _opt(req, 'tg', tg_def, -20, 80, 'Ambient temperature')
    for cb in types:
        if tg >= cb['theta']:
            raise InputRejected(f"Ambient {tg} C is at/above the maximum conductor temperature of "
                                f"{cb['desig']} ({cb['theta']} C).")
    rho_e = 1.0; air_mode = None; duct = None; bank = None; banks = None; rho_native = None
    bank_map = None; trough = None; layers = None; solar = None; h_factor = 1.0
    trough_flag = False; backfill_rho_val = None
    placed = []
    notes = []

    def _type(i):
        i = int(i)
        if not 0 <= i < len(types):
            raise InputRejected(f'Cable type index {i} does not exist.')
        return types[i]

    if inst == '3':
        a = req.get('air') or {}
        for i, circ in enumerate(a.get('circuits') or [], 1):
            ct = _type(circ['type'])
            if ct['n'] == 1:
                fm = circ.get('formation') or 'trefoil'
                if fm not in ('trefoil', 'flat_touching', 'flat_spaced'):
                    raise InputRejected('Formation must be trefoil, flat_touching or flat_spaced.')
                sp = _rng('centre-centre spacing', circ['spacing'], 20, 2000) if fm == 'flat_spaced' else None
            else:
                fm, sp = '3core', None
            placed += L._expand_circuit(ct, (i - 1) * 1000.0, 0.0, fm, f'C{i}', sp)
        air_mode = (placed[0]['formation'] if placed and placed[0]['formation'] not in ('3core',)
                    else 'single')
        dd = a.get('ducts')
        if dd:
            _Do = _rng('duct outer diameter', dd['Do'], 50, 600)
            _Dd = _rng('duct inner diameter', dd['Dd'], 30, _Do)
            _rd = _opt(dd, 'rho_d', 3.5, 0.3, 8, 'duct wall rho')
            _nd = int(_opt(dd, 'n_in_duct', 3, 1, 3, 'cables per duct'))
            _rf = _opt(dd, 'rho_fill', 1.2, 0.3, 6, 'filling rho') if dd.get('filled') else None
            _thm = _opt(dd, 'thm', 60.0, 20, 120, 'mean duct medium temperature')
            duct = (_Do, _Dd, _rd, _thm, _rf)
            for _p in placed:
                _p['n_in_duct'] = _nd
        tr = a.get('trough')
        if tr:
            trough = (_rng('trough width', tr['w'], 0.1, 10), _rng('trough height', tr['h'], 0.1, 10))
        h_factor = _opt(a, 'h_factor', 1.0, 0.3, 2.0, 'h multiplier')
        so = a.get('solar')
        if so:
            solar = (_opt(so, 'sigma', 0.4, 0.1, 1.0, 'solar absorption'),
                     _opt(so, 'H', 1000.0, 100, 1400, 'solar intensity'))
            notes.append('Solar term follows IEC 60287-1-1 eq.(4) but is NOT calibrated against a '
                         'CYMCAP export - treat as indicative.')
        if h_factor == 1.0 and (trough or duct):
            notes.append('h uses the single-group IEC correlation; CYMCAP reduces it for stacked '
                         'groups, so stacked arrangements may be slightly optimistic.')
    elif inst == '2':
        dq = req.get('duct') or {}
        rho_e = _opt(dq, 'rho_e', std['rho_soil'], 0.3, 6, 'Soil / backfill rho')
        banks = _bank_coords(dq.get('banks') or [])
        if not banks:
            raise InputRejected('Define at least one duct bank.')
        if len(banks) > 1:
            rho_native = _opt(dq, 'rho_native', rho_e, 0.3, 8, 'native soil rho')
        Do = _rng('Duct OD', dq['Do'], 50, 500)
        Dd = _rng('Duct ID', dq['Dd'], 40, 480)
        if Dd >= Do:
            raise InputRejected('Duct ID must be smaller than duct OD.')
        rho_d = _opt(dq, 'rho_d', 6.0, 1, 12, 'Duct rho')
        thm = _opt(dq, 'thm', 60.0, 30, 95, 'Mean medium temp in duct')
        fill = dq.get('fill') or 'air'
        rho_fill = _opt(dq, 'rho_fill', 1.2, 0.3, 6, 'duct filling rho') if fill == 'filled' else None
        duct_fill_zero = (fill == 'zero')
        duct = (Do, Dd, rho_d, thm, rho_fill)
        bank_map = {}
        model = dq.get('soil_model') or 'none'
        if model == 'layers':
            layers = []
            for ly in dq.get('layers') or []:
                layers.append((_rng('layer X', ly['X'], -50, 50), _rng('layer Y', ly['Y'], 0.01, 20),
                               _rng('layer width', ly['W'], 0.01, 50), _rng('layer height', ly['H'], 0.01, 20),
                               _rng('layer rho', ly['rho'], 0.2, 6)))
            if not layers:
                layers = None
        elif model == 'bank':
            for bk in banks:
                e = (dq.get('bank_map') or {}).get(str(bk['id'])) or {}
                if e.get('direct_rho') not in (None, ''):
                    bank_map[bk['id']] = float(e['direct_rho'])
                    continue
                Nl = int(_rng('N loaded cables', e['Nl'], 1, 40))
                LG = _rng('bank centre depth LG', e['LG'], 200, 8000)
                xb = _rng('bank shorter side', e['xb'], 100, 8000)
                yb = _rng('bank longer side', e['yb'], xb, 12000)
                rc = _rng('bank rho', e['rc'], 0.3, 3)
                bank_map[bk['id']] = (Nl, LG, xb, yb, rc)
            bank = next((v for v in bank_map.values() if isinstance(v, tuple)), None)
        n_in_duct = int(dq.get('n_in_duct') or 3)
        if n_in_duct not in (1, 2, 3):
            raise InputRejected('Single-core cables per duct must be 1, 2 or 3.')
        by_bank = {bk['id']: bk for bk in banks}
        used = set()
        # same order as place_cables_in_banks(): bank, then row, then column
        _positions = sorted(dq.get('positions') or [],
                            key=lambda q: (int(q['bank']), int(q['row']), int(q['col'])))
        for pos in _positions:
            bk = by_bank.get(int(pos['bank']))
            if not bk:
                raise InputRejected(f"Position refers to bank {pos['bank']} which does not exist.")
            r, c = int(pos['row']), int(pos['col'])
            if (r, c) not in bk['coords']:
                raise InputRejected(f"B{bk['id']} R{r}-C{c} is outside the bank grid.")
            if (bk['id'], r, c) in used:
                raise InputRejected(f"B{bk['id']} R{r}-C{c} is assigned twice.")
            used.add((bk['id'], r, c))
            x, y = bk['coords'][(r, c)]
            _ct = _type(pos['type'])
            load = pos.get('load')
            load = float(load) if load not in (None, '') else None
            if load is not None and load < 0:
                raise InputRejected('Operating load cannot be negative.')
            _n = n_in_duct if _ct['n'] == 1 else 1
            placed.append(dict(cb=_ct, x=x, y=y, tag=f"B{bk['id']}R{r}C{c}", bank_id=bk['id'],
                               n_in_duct=_n, load=load))
        for p in placed:
            p['duct_fill_zero'] = duct_fill_zero
    else:
        bq = req.get('buried') or {}
        rho_e = _opt(bq, 'rho_e', std['rho_soil'], 0.3, 6, 'Soil rho')
        Lmm = _rng('Depth to circuit centres', bq['L'], 200, 5000)
        rho_native = rho_e
        if bq.get('trough_rho') not in (None, ''):
            trough_flag = True
            tr = _rng('trough fill rho', bq['trough_rho'], 0.3, 3)
            rho_native = rho_e
            rho_e = tr
        elif bq.get('backfill_rho') not in (None, ''):
            rho_bf = _rng('backfill rho', bq['backfill_rho'], 0.3, 3)
            backfill_rho_val = rho_bf
            rho_native = rho_e
            rho_e = rho_bf
        for i, circ in enumerate(bq.get('circuits') or [], 1):
            ct = _type(circ['type'])
            x = _rng('circuit centre x', circ['x'], -20000, 20000)
            if ct['n'] == 1:
                fm = circ.get('formation') or 'trefoil'
                if fm not in ('trefoil', 'flat_touching', 'flat_spaced'):
                    raise InputRejected('Formation must be trefoil, flat_touching or flat_spaced.')
                sp = _rng('centre-centre spacing', circ['spacing'], 20, 2000) if fm == 'flat_spaced' else None
            else:
                fm, sp = '3core', None
            placed += L._expand_circuit(ct, x, Lmm, fm, f'C{i}', sp)

    if not placed:
        raise InputRejected('No cables placed.')
    # overlap check (physical consistency of the entered layout)
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a_, b_ = placed[i], placed[j]
            dmin = 0.5 * (a_['cb']['De'] + b_['cb']['De'])
            if inst == '2':
                dmin = duct[0]
            if math.hypot(a_['x'] - b_['x'], a_['y'] - b_['y']) < dmin - 1e-6:
                raise InputRejected(f"{a_['tag']} and {b_['tag']} overlap "
                                    f"(centre distance below {dmin:.0f} mm).")

    if inst == '3':
        formation = placed[0].get('formation', 'trefoil')
    elif inst == '2':
        formation = 'ducts'
    else:
        formation = placed[0]['formation'] if placed else 'trefoil'
    for p in placed:
        p.setdefault('formation', formation)

    ctx = dict(std_key=std_key, std=std, types=types, infos=infos, inst=inst, inst_name=inst_name,
               tg=tg, rho_e=rho_e, air_mode=air_mode, duct=duct, bank=bank, banks=banks,
               rho_native=rho_native, bank_map=bank_map, trough=trough, layers=layers, solar=solar,
               h_factor=h_factor, trough_flag=trough_flag, backfill_rho_val=backfill_rho_val,
               formation=formation, notes=notes)
    return placed, ctx


def _post(req: dict, placed: list, ctx: dict) -> list:
    """Per-cable electrical/sequence/induced/short-circuit/emergency set, as in
    mode4_full_report() after the solver."""
    Lroute = _rng('Route length', req.get('Lroute', 1000), 1, 100000)
    rho_earth = _opt(req, 'rho_earth', 100.0, 1, 10000, 'Earth resistivity')
    t_sc = _opt(req, 't_sc', 1.0, 0.1, 5, 'Short-circuit duration')
    If_sc = _rng('Earth-fault level', req.get('If_sc', 31.5), 0.1, 100)
    do_emerg = ctx['inst'] == '1' and bool(req.get('emergency'))
    theta_em = _opt(req, 'theta_em', 105.0, 90, 160, 'Emergency conductor temperature') if do_emerg else 105.0
    reports = []
    for p in placed:
        c = p['cb']; I = p['load'] if p['load'] else p['I']
        _sax = L.axial_spacing(c)
        el = L.calc_electrical(c, I=I, s=_sax)
        se = L.calc_sequence(c, s=_sax, rho_earth=rho_earth)
        ind = L.calc_induced(c, I, Lroute, s=_sax)
        ad = L.suite_adiabatic(c, t=t_sc, If=If_sc, quiet=True)
        em = None
        if do_emerg:
            T1, T2, T3, _ = L.cable_thermal(c)
            T4 = p.get('T4', 1.0)
            em = L.emergency_rating(c, T1, T2, T3, T4, rho_T=ctx['rho_e'], L_m=p['y'] / 1000.0,
                                    s_m=c['De'] / 1000.0, theta_soil=ctx['tg'], theta_E=theta_em,
                                    IR_cont=p['I'])
        reports.append(dict(p=p, I=I, el=el, se=se, ind=ind, ad=ad, em=em))
    return reports


_P_KEYS = ('tag', 'x', 'y', 'T1', 'T2', 'T3', 'T4', 'R', 'lam1', 'lam2', 'Wd', 'I', 'theta_op',
           'dt_int', 'dtheta', 'rho_ext', 'n_in_duct', 'formation', 'spacing', 'load', 'bank_id',
           'dt_trough', 'dt_solar', 'dtheta_s', 's_for_R')


def run_full_report(req: dict) -> dict:
    with run_engine() as run:
        placed, ctx = prepare_arrangement(req)
        L.solve_arrangement_xy(placed, ctx['rho_e'], ctx['air_mode'], ctx['tg'], ctx['duct'],
                               ctx['bank'], rho_native=ctx['rho_native'], bank_map=ctx['bank_map'],
                               trough=ctx['trough'], layers=ctx['layers'], solar=ctx['solar'],
                               h_factor=ctx['h_factor'])
        reports = _post(req, placed, ctx)
        type_index = {id(t): i for i, t in enumerate(ctx['types'])}
        cables_out = [describe_cable(t, info) for t, info in zip(ctx['types'], ctx['infos'])]

    bad = find_non_finite([{k: p.get(k) for k in _P_KEYS} for p in placed])
    if bad:
        raise InputRejected('The solver produced non-finite values for this arrangement '
                            f'({len(bad)} values). Check geometry and resistivities.')
    pl_out = []
    over = []
    for p in placed:
        d = {k: p.get(k) for k in _P_KEYS}
        d['type'] = type_index[id(p['cb'])]
        d['desig'] = p['cb']['desig']
        d['n'] = p['cb']['n']
        d['De'] = p['cb']['De']
        d['theta_max'] = p['cb']['theta']
        d['over_limit'] = (p.get('load') is not None and
                           p.get('theta_op', p['cb']['theta']) > p['cb']['theta'] + 0.05)
        d['pts'] = p.get('pts')
        if d['over_limit']:
            over.append(p['tag'])
        if p['I'] <= 0.1:
            d['zero_rating'] = True
        pl_out.append(to_jsonable(d))
    rep_out = []
    for rp in reports:
        rep_out.append(to_jsonable({'tag': rp['p']['tag'], 'I': rp['I'], 'electrical': rp['el'],
                                    'sequence': rp['se'], 'induced': rp['ind'],
                                    'short_circuit': rp['ad'], 'emergency': rp['em']}))
    warnings = list(ctx['notes'])
    for t, info in zip(ctx['types'], ctx['infos']):
        for k in ('warning_no_screen', 'warning_De'):
            if info.get(k):
                warnings.append(f"{t['desig']}: {info[k]}")
        if info.get('G_extrapolated') and t.get('n') == 3 and t.get('n3_construction') == 'screened':
            warnings.append(f"{t['desig']}: Fig.6 G fit validated for t/d 0.045-0.06 only "
                            f"(here {info['t_over_d']:.4f}) - read G off Figure 6 for accuracy.")
    multibank = ctx['banks'] is not None and len(ctx['banks']) > 1
    if multibank:
        warnings.append('MULTI-BANK ESTIMATE - NOT VALIDATED AGAINST CYMCAP. Treat ratings as '
                        'engineering estimates and cross-check one case independently.')
    if any(t.get('n') == 3 and t.get('n3_construction') == 'screened' for t in ctx['types']):
        warnings.append('Screened 3-core: remaining bias is the effective soil resistivity '
                        '(Neher single-rectangle model). Enter a CYMCAP/FEA effective rho on backfill '
                        'or multi-bank jobs. lambda2 runs ~55% low vs CIGRE-guidance studies '
                        '(~0.3% on rating).')
    if any(t.get('n') == 3 and t.get('n3_construction') == 'belted' for t in ctx['types']):
        warnings.append('Belted 3-core: lambda1 is reduced by a fixed x0.1 factor in the original '
                        'engine (approximation).')
    if over:
        warnings.append('At least one conductor exceeds its maximum temperature at the loads '
                        'entered: ' + ', '.join(over))
    for rp in rep_out:
        if not rp['short_circuit']['adequate']:
            warnings.append(f"{rp['tag']}: metallic-layer short-circuit withstand REVIEW REQUIRED.")
        if rp['induced']['V_tref'] > 65:
            warnings.append(f"{rp['tag']}: standing sheath voltage {rp['induced']['V_tref']:.0f} V "
                            'exceeds the common 65 V touch limit (check SVL / bonding design).')
    gov = min(pl_out, key=lambda q: q['I'])
    banks_out = None
    if ctx['banks']:
        banks_out = [{k: v for k, v in b.items() if k != 'coords'} |
                     {'coords': [{'row': r, 'col': c, 'x': xy[0], 'y': xy[1]}
                                 for (r, c), xy in b['coords'].items()]} for b in ctx['banks']]
    return {
        'mode': 'advanced_mvhv',
        'engine_version': ENGINE_VERSION,
        'standard': {'key': ctx['std_key'], **ctx['std']},
        'installation': ctx['inst_name'],
        'formation': ctx['formation'],
        'air_mode': ctx['air_mode'],
        'tg': ctx['tg'], 'rho_e': ctx['rho_e'], 'rho_native': ctx['rho_native'],
        'duct': ctx['duct'], 'bank': ctx['bank'],
        'bank_map': {str(k): v for k, v in (ctx['bank_map'] or {}).items()},
        'trough': ctx['trough'], 'layers': ctx['layers'], 'solar': ctx['solar'],
        'h_factor': ctx['h_factor'], 'trough_flag': ctx['trough_flag'],
        'backfill_rho': ctx['backfill_rho_val'],
        'banks': banks_out,
        'cables': cables_out,
        'placed': pl_out,
        'reports': rep_out,
        'governing': {'tag': gov['tag'], 'I': gov['I'], 'desig': gov['desig']},
        'multibank_unvalidated': multibank,
        'warnings': warnings + run.warnings,
        'engine_messages': run.messages,
    }


def sensitivity(req: dict) -> dict:
    """Data behind the original _sensitivity_tables(): depth, soil rho and
    load-factor sweeps for the governing cable, same calls and same grids."""
    with run_engine():
        placed, ctx = prepare_arrangement(req)
        if ctx['air_mode']:
            raise InputRejected('The original sensitivity study covers buried and duct installations only.')
        L.solve_arrangement_xy(placed, ctx['rho_e'], ctx['air_mode'], ctx['tg'], ctx['duct'],
                               ctx['bank'], rho_native=ctx['rho_native'], bank_map=ctx['bank_map'],
                               trough=ctx['trough'], layers=ctx['layers'], solar=ctx['solar'],
                               h_factor=ctx['h_factor'])
        gov = min(placed, key=lambda p: p['I'])
        c = gov['cb']; duct = ctx['duct']; bank = ctx['bank']; rho_e = ctx['rho_e']; tg = ctx['tg']
        T1, T2, T3, _ = L.cable_thermal(c)
        R = gov['R']; lam1 = gov.get('lam1', 0); lam2 = gov.get('lam2', 0); Wd = gov['Wd']
        base_L = gov['y']

        def T4_at(Lmm, rho):
            if not duct:
                return L.iec_T4_buried_trefoil(Lmm, rho, c['De'], c['De'], [])
            return L.iec_T4_duct(Lmm, rho, c['De'], duct[0], duct[1], duct[2], duct[3], [], 0.0, bank)

        def I_at(T4):
            return L.iec_rating(c['theta'] - tg, Wd, R, c['n'], T1, T2, T3, T4, lam1, lam2)
        depth = [{'x': d, 'I': I_at(T4_at(d * 1000, rho_e))} for d in [0.5, 0.8, 1.0, 1.5, 2.0]]
        rho = [{'x': r, 'I': I_at(T4_at(base_L, r))} for r in [0.8, 1.0, 1.5, 2.0, 2.5, 3.0]]
        lf = []
        for f_ in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            mu = f_ + (1 - f_) * 0.3
            lf.append({'x': f_, 'I': L.iec_rating(c['theta'] - tg, Wd, R, c['n'], T1, T2, T3,
                                                  T4_at(base_L, rho_e) * mu, lam1, lam2)})
    return to_jsonable({'governing': gov['tag'], 'desig': c['desig'], 'base_rating': gov['I'],
                        'depth': depth, 'rho': rho, 'load_factor': lf,
                        'notes': ['Single-cable sweeps without mutual heating, exactly as the '
                                  'original report table (it re-evaluates T4 for the governing '
                                  'cable alone).',
                                  'Load-factor sweep uses the original simplified mu = LF + 0.3(1-LF) '
                                  'scaling of T4 - indicative, not an IEC 60853 cyclic rating.']})


def isotherm_field(result: dict, cols=60, rows=24) -> dict:
    """The original _draw_isotherms() field as data (indicative superposed
    point-source rise, NOT a finite-element solution)."""
    pl = result['placed']
    if result.get('air_mode') or not pl:
        return {'available': False}
    xs = [p['x'] for p in pl]; ys = [p['y'] for p in pl]
    minx, maxx = min(xs) - 400, max(xs) + 400
    miny, maxy = 0, max(ys) + 500
    rho_e = result['rho_e']
    grid = []
    for j in range(rows):
        Y = miny + (j + 0.5) * (maxy - miny) / rows
        line = []
        for i in range(cols):
            X = minx + (i + 0.5) * (maxx - minx) / cols
            s = 0.0
            for p in pl:
                Wc = p['n'] * (p['I'] ** 2 * p['R'] / 1000 * (1 + (p.get('lam1') or 0) + (p.get('lam2') or 0)))
                dd = max(math.hypot(X - p['x'], Y - p['y']), p['De'] / 2)
                dimg = math.hypot(X - p['x'], Y + p['y'])
                s += Wc * rho_e / (2 * math.pi) * math.log(dimg / dd)
            line.append(s)
        grid.append(line)
    return {'available': True, 'minx': minx, 'maxx': maxx, 'miny': miny, 'maxy': maxy,
            'cols': cols, 'rows': rows, 'grid': grid, 'tg': result['tg'],
            'note': 'Indicative superposed temperature rise (steady-state image approximation); '
                    'for visualisation, not a finite-element field.'}


def generate_pdf(req: dict, pdf_dir: str, project: dict) -> str:
    answers = [latin1(project.get('name', '')), latin1(project.get('client', '')),
               latin1(project.get('ref', ''))]
    with run_engine(answers=answers, pdf_dir=pdf_dir) as run:
        placed, ctx = prepare_arrangement(req)
        L.solve_arrangement_xy(placed, ctx['rho_e'], ctx['air_mode'], ctx['tg'], ctx['duct'],
                               ctx['bank'], rho_native=ctx['rho_native'], bank_map=ctx['bank_map'],
                               trough=ctx['trough'], layers=ctx['layers'], solar=ctx['solar'],
                               h_factor=ctx['h_factor'])
        reports = _post(req, placed, ctx)
        for t in ctx['types']:   # PDF uses core fonts
            t['desig'] = latin1(t['desig'])
        L.generate_mode4_pdf(ctx['types'], placed, reports, ctx['inst'], ctx['air_mode'], ctx['banks'],
                             ctx['rho_e'], ctx['tg'], ctx['duct'], ctx['bank'],
                             formation=ctx['formation'], rho_native=ctx['rho_native'],
                             trough_flag=ctx['trough_flag'], backfill_rho_val=ctx['backfill_rho_val'],
                             std=ctx['std'])
    if not run.pdf_file:
        raise RuntimeError('legacy Mode 4 PDF generator did not write a file')
    return run.pdf_file


PRESETS = {
    'ref_132kv_1x400': {
        'label': 'Example: 1x400 Cu 132 kV, Cu wire + lead sheath (illustrative, after the workbook cable)',
        'cable': {'desig': '1x400', 'mat': 'CU', 'U': 132, 'f': 50, 'theta': 90, 'dc': 23.2,
                  'tcs': 1.0, 'ti': 20.5, 'tis': 1.0, 'rho_ins': 3.5, 'theta_scr': 85,
                  'cu_wire': {'dw': 2.81, 'N': 63}, 'lead': {'tl': 2.8}, 't_bed': 1.0,
                  'rho_bed': 3.5, 'tj': 4.5, 'rho_j': 3.5, 'insulation': 'XLPE', 'bonding': 'single'},
    },
    'mv_33kv_1x630_awa': {
        'label': 'Example: 1x630 Cu 33 kV, Cu tape, AWA (illustrative)',
        'cable': {'desig': '1x630', 'mat': 'CU', 'U': 33, 'f': 50, 'theta': 90, 'dc': 30.05,
                  'tcs': 1.0, 'ti': 8.0, 'tis': 0.9, 'rho_ins': 3.5, 'theta_scr': 87.5,
                  'cu_tape': {'tt': 0.076, 'wt': 50, 'double': False}, 't_bed': 1.6, 'rho_bed': 3.5,
                  'armour': {'type': 'AWA', 'da': 2.5, 'Na': 60}, 'tj': 3.0, 'rho_j': 3.5,
                  'insulation': 'XLPE', 'bonding': 'both_ends'},
    },
    'mv_33kv_3x240_sl': {
        'label': 'Example: 3x240 Cu 33 kV SL-type, SWA (illustrative)',
        'cable': {'desig': '3x240', 'mat': 'CU', 'U': 33, 'f': 50, 'theta': 90, 'dc': 18.1,
                  'tcs': 0.9, 'ti': 8.0, 'tis': 0.9, 'rho_ins': 3.5, 'theta_scr': 87.1,
                  'cu_tape': {'tt': 0.1, 'wt': 30, 'double': False}, 'n3_construction': 'screened',
                  'rho_filler': 5.0, 't2': 2.0, 't_bed': 2.0, 'rho_bed': 3.5,
                  'armour': {'type': 'SWA', 'da': 2.5, 'Na': 60}, 'tj': 3.7, 'rho_j': 5.0,
                  'insulation': 'XLPE', 'bonding': 'both_ends'},
    },
}
