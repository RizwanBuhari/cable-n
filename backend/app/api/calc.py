"""Stateless calculation endpoints. Inputs arrive with each request; the
engine result is returned and nothing is stored on the server."""
from __future__ import annotations

import copy

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError

from ..core.config import get_settings
from ..core.protect import rate_limit, run_bounded
from ..engine import legacy_engine as L
from ..engine import mode1, mode4
from ..engine.mode1 import InputRejected
from ..engine.runtime import ENGINE_VERSION, EngineInputRequired, run_engine
from ..reports import excel
from ..services import jobs
from ..services.calculations import MODES, compute, summarise, validate_inputs

router = APIRouter(prefix='/calculations', tags=['calculations'])
jobs_router = APIRouter(prefix='/jobs', tags=['jobs'])

SLUGS = {'single-feeder': 'single_feeder', 'batch': 'batch', 'current-rating': 'current_rating',
         'advanced-mvhv': 'advanced_mvhv'}
SLUG_OF = {v: k for k, v in SLUGS.items()}
VERIFICATION_NOTICE = ('Calculated by a deterministic engine from the inputs shown. Passing numerical checks is '
                       'not design approval - verification by a qualified electrical engineer is required before '
                       'use.')
MAX_M4_CABLES = 72


def bad_request(e: Exception):
    """Map engine / validation errors to 422 with readable messages."""
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, ValidationError):
        msgs = []
        for err in e.errors():
            loc = '.'.join(str(x) for x in err['loc'] if x != '__root__')
            msgs.append(f"{loc}: {err['msg']}" if loc else err['msg'])
        raise HTTPException(422, {'message': 'Input validation failed', 'errors': msgs})
    if isinstance(e, (InputRejected, EngineInputRequired)):
        raise HTTPException(422, {'message': str(e), 'errors': [str(e)]})
    if isinstance(e, (ValueError, KeyError, TypeError, ZeroDivisionError)):
        msg = f'missing input {e}' if isinstance(e, KeyError) else str(e)
        raise HTTPException(422, {'message': 'The engine rejected these inputs', 'errors': [msg]})
    raise e


def check_size(mode: str, clean: dict):
    s = get_settings()
    if mode == 'batch' and len(clean['feeders']) > s.BATCH_MAX_FEEDERS:
        raise HTTPException(422, {'message': f'At most {s.BATCH_MAX_FEEDERS} feeders per schedule on the public '
                                             'site.', 'errors': []})
    if mode == 'advanced_mvhv':
        n = 0
        inst = clean['installation']
        if inst == 'duct':
            n = len((clean.get('duct') or {}).get('positions') or []) * 3
        else:
            n = len(((clean.get(inst) or {}).get('circuits')) or []) * 3
        if n > MAX_M4_CABLES:
            raise HTTPException(422, {'message': f'Arrangement too large for the public site (max '
                                                 f'{MAX_M4_CABLES // 3} circuits / duct positions).', 'errors': []})


def engine_run(mode: str, inputs: dict) -> tuple[dict, dict]:
    try:
        clean = validate_inputs(mode, inputs)
    except Exception as e:  # noqa: BLE001
        bad_request(e)
    check_size(mode, clean)

    def work():
        return compute(mode, clean)
    try:
        result = run_bounded(work)
    except Exception as e:  # noqa: BLE001
        bad_request(e)
    result['verification_notice'] = VERIFICATION_NOTICE
    result['run_status'] = 'executed'
    return clean, result


# ---------------------------------------------------------------- metadata
@router.get('/modes')
def modes():
    return [{'mode': m, 'slug': SLUG_OF[m], 'label': lbl} for m, (lbl, _) in MODES.items()]


class RunIn(BaseModel):
    inputs: dict


def _make_mode_route(slug: str):
    mode = SLUGS[slug]

    def endpoint(body: RunIn, request: Request):
        rate_limit(request, 'calc', get_settings().CALC_RATE_PER_MINUTE)
        clean, result = engine_run(mode, body.inputs)
        return {'mode': mode, 'inputs': clean, 'result': result, 'summary': summarise(mode, clean, result),
                'engine_version': ENGINE_VERSION}
    endpoint.__name__ = f'run_{mode}'
    endpoint.__doc__ = f'Run the {MODES[mode][0]} engine. Nothing is stored.'
    router.add_api_route(f'/{slug}', endpoint, methods=['POST'], name=f'run_{mode}')


for _slug in SLUGS:
    _make_mode_route(_slug)


class OptionsIn(BaseModel):
    material: str = Field(pattern='^(cu|al)$')
    armored: bool
    core_type: str = Field(pattern='^(1C|3C)$')
    installation: str = Field(pattern='^(buried|duct|air)$')


@router.post('/single-feeder/arrangements')
def arrangements(body: OptionsIn):
    try:
        return mode1.options_for(body.model_dump())
    except Exception as e:  # noqa: BLE001
        bad_request(e)


class CablePreviewIn(BaseModel):
    cable: dict
    standard: str = 'IEC'


@router.post('/advanced-mvhv/cable-preview')
def cable_preview(body: CablePreviewIn, request: Request):
    """What define_cable() prints while you type: derived diameters, T1-T3, Wd, G."""
    rate_limit(request, 'calc', get_settings().CALC_RATE_PER_MINUTE)
    try:
        with run_engine():
            cb, info = mode4.build_cable(body.cable, L.STANDARDS.get(body.standard))
            return mode4.describe_cable(cb, info)
    except Exception as e:  # noqa: BLE001
        bad_request(e)


@router.get('/advanced-mvhv/presets')
def presets():
    return {'presets': mode4.PRESETS, 'standards': L.STANDARDS}


class InputsIn(BaseModel):
    inputs: dict


@router.post('/advanced-mvhv/sensitivity')
def mode4_sensitivity(body: InputsIn, request: Request):
    """The original report's sensitivity tables (depth / soil rho / load factor)."""
    rate_limit(request, 'calc', get_settings().CALC_RATE_PER_MINUTE)
    try:
        clean = validate_inputs('advanced_mvhv', body.inputs)
        check_size('advanced_mvhv', clean)
        return run_bounded(mode4.sensitivity, clean)
    except Exception as e:  # noqa: BLE001
        bad_request(e)


@router.post('/advanced-mvhv/isotherms')
def mode4_isotherms(body: InputsIn, request: Request):
    rate_limit(request, 'calc', get_settings().CALC_RATE_PER_MINUTE)
    _, res = engine_run('advanced_mvhv', body.inputs)
    return mode4.isotherm_field(res)


# ---------------------------------------------------------------- sensitivity / what-if
SWEEPABLE = {
    'single_feeder': {
        'air_temp': 'Ambient air temperature (°C)', 'soil_temp': 'Soil temperature (°C)',
        'soil_resistivity': 'Soil thermal resistivity (K·m/W)', 'duct_resistivity': 'Duct thermal resistivity (K·m/W)',
        'depth': 'Burial depth (m)', 'cable_length': 'Cable length (m)', 'current': 'Load current (A)',
        'power': 'Load power', 'power_factor': 'Power factor', 'voltage_drop_limit_pct': 'Voltage-drop limit (%)',
    },
    'current_rating': {'soil_rho': 'Soil thermal resistivity (K·m/W)', 'soil_temp': 'Soil temperature (°C)'},
    'advanced_mvhv': {'tg': 'Ambient temperature (°C)', 'rho_e': 'Soil thermal resistivity (K·m/W)',
                      'depth': 'Depth to circuit centres (mm)', 'spacing': 'Flat-spaced spacing (mm)'},
}
SUPPORTED_RANGES = {
    'soil_resistivity': (0.7, 3.0, 'rating-factor table range; the nearest tabled value is used outside it'),
    'duct_resistivity': (0.7, 3.0, 'rating-factor table range; the nearest tabled value is used outside it'),
    'depth': (0.5, 3.0, 'depth-factor table range; the nearest tabled value is used outside it'),
}


class SweepIn(BaseModel):
    mode: str
    inputs: dict
    variable: str
    values: list[float] = Field(min_length=1, max_length=40)


def _set_var(mode, inputs, var, v):
    p = copy.deepcopy(inputs)
    if mode == 'advanced_mvhv':
        inst = p.get('installation')
        if var == 'tg':
            p['tg'] = v
        elif var == 'rho_e':
            p.setdefault(inst, {})['rho_e'] = v
        elif var == 'depth':
            if inst == 'buried':
                p['buried']['L'] = v
            elif inst == 'duct':
                for b in p['duct']['banks']:
                    b['top'] = v / 1000.0
            else:
                raise InputRejected('Depth does not apply to installations in air.')
        elif var == 'spacing':
            hit = False
            for c in (p.get(inst) or {}).get('circuits') or []:
                if c.get('formation') == 'flat_spaced':
                    c['spacing'] = v
                    hit = True
            if not hit:
                raise InputRejected('A spacing sweep needs at least one flat-spaced circuit.')
    else:
        p[var] = v
    return p


def sweep_metrics(mode, res):
    if mode == 'single_feeder':
        s = res.get('single')
        if s:
            r = s['recommended']
            c = r['chain']
            return {'feasible': True, 'size': r['size'], 'runs': 1, 'derated_current': r['derated_current'],
                    'utilisation': r['utilisation'], 'voltage_drop': r['voltage_drop'],
                    'total_factor': c['ambient'] * c['soil'] * c['depth'] * c['group'],
                    'design_current': res['design_current'], 'governing': s['governing']}
        if res['best_by_spacing']:
            b = min(res['best_by_spacing'], key=lambda x: (x['runs'], float(x['size'])))
            return {'feasible': True, 'size': b['size'], 'runs': b['runs'], 'derated_current': b['derated_current'],
                    'utilisation': b['utilisation'], 'voltage_drop': b['voltage_drop'],
                    'design_current': res['design_current'], 'governing': b['governing'], 'spacing': b['spacing']}
        return {'feasible': False, 'design_current': res['design_current']}
    if mode == 'current_rating':
        return {'min_rating': res['summary']['min_rating'], 'positions': {p['pos']: p['iz'] for p in res['positions']}}
    if mode == 'advanced_mvhv':
        g = res['governing']
        return {'governing_rating': g['I'], 'governing_tag': g['tag'],
                'max_theta': max(p['theta_op'] for p in res['placed'])}
    return {}


@router.get('/sensitivity/variables')
def sweep_vars():
    return SWEEPABLE


@router.post('/sensitivity')
def sensitivity(body: SweepIn, request: Request):
    """Re-runs the deterministic engine at each value - every point is a real
    engine result; nothing is interpolated or extrapolated."""
    s = get_settings()
    rate_limit(request, 'calc', s.CALC_RATE_PER_MINUTE)
    if body.mode not in SWEEPABLE or body.variable not in SWEEPABLE[body.mode]:
        raise HTTPException(422, {'message': 'This variable cannot be swept for this mode', 'errors': []})
    values = sorted(set(body.values))
    if len(values) > s.SWEEP_MAX_POINTS:
        raise HTTPException(422, {'message': f'At most {s.SWEEP_MAX_POINTS} sweep points.', 'errors': []})
    rng = SUPPORTED_RANGES.get(body.variable) if body.mode == 'single_feeder' else None

    def work():
        pts = []
        for v in values:
            try:
                p = _set_var(body.mode, body.inputs, body.variable, v)
                clean = validate_inputs(body.mode, p)
                check_size(body.mode, clean)
                pt = {'x': v, 'ok': True, **sweep_metrics(body.mode, compute(body.mode, clean))}
            except HTTPException as e:
                pt = {'x': v, 'ok': False, 'error': str(e.detail)[:300]}
            except Exception as e:  # noqa: BLE001 - recorded per point
                msg = '; '.join(x['msg'] for x in e.errors()) if isinstance(e, ValidationError) else str(e)
                pt = {'x': v, 'ok': False, 'error': msg[:300]}
            if rng and not (rng[0] <= v <= rng[1]):
                pt['outside_supported_range'] = True
            pts.append(pt)
        return pts
    points = run_bounded(work)
    warnings = []
    if rng and any(p.get('outside_supported_range') for p in points):
        warnings.append(f'{SWEEPABLE[body.mode][body.variable]}: values outside {rng[0]}-{rng[1]} use the {rng[2]} '
                        '- the curve is flat there by construction, not physically.')
    return {'variable': body.variable, 'label': SWEEPABLE[body.mode][body.variable], 'points': points,
            'warnings': warnings, 'engine_version': ENGINE_VERSION}


# ---------------------------------------------------------------- cost estimate
class CostLine(BaseModel):
    label: str = Field(max_length=120)
    size: str = Field(max_length=20)
    runs: int = Field(ge=1, le=50)
    cables_per_run: int = Field(1, ge=1, le=6)
    length_m: float = Field(gt=0, le=200000, allow_inf_nan=False)
    cost_per_m: float = Field(ge=0, allow_inf_nan=False)
    install_cost: float = Field(0, ge=0, allow_inf_nan=False)
    duct_cost: float = Field(0, ge=0, allow_inf_nan=False)
    other_cost: float = Field(0, ge=0, allow_inf_nan=False)
    material: str = Field('cu', pattern='^(cu|al)$')
    load_current_A: float | None = Field(None, ge=0, allow_inf_nan=False)
    phases: int = Field(3, ge=1, le=3)
    loss_load_factor: float | None = Field(None, ge=0, le=1, allow_inf_nan=False)
    hours_per_year: float = Field(8760, ge=0, le=8784, allow_inf_nan=False)
    tariff_per_kwh: float | None = Field(None, ge=0, allow_inf_nan=False)
    years: int = Field(1, ge=1, le=60)


class CostIn(BaseModel):
    currency: str = Field('', max_length=10)
    lines: list[CostLine] = Field(min_length=1, max_length=20)


@router.post('/cost-estimate')
def cost_estimate(body: CostIn, request: Request):
    """Arithmetic on USER-SUPPLIED prices only. Energy loss uses the engine's
    own conductor resistance table at the stated current:
    P = phases x I_run^2 x R x L x runs. No market prices exist in Cable-N."""
    rate_limit(request, 'calc', get_settings().CALC_RATE_PER_MINUTE)
    out = []
    for ln in body.lines:
        cable_m = ln.length_m * ln.runs * ln.cables_per_run
        capex = cable_m * ln.cost_per_m + ln.install_cost + ln.duct_cost + ln.other_cost
        row = {'label': ln.label, 'cable_length_total_m': cable_m, 'cable_cost': cable_m * ln.cost_per_m,
               'install_cost': ln.install_cost, 'duct_cost': ln.duct_cost, 'other_cost': ln.other_cost,
               'capex': capex, 'assumptions': [f'{ln.runs} run(s) x {ln.cables_per_run} cable(s) per run x '
                                               f'{ln.length_m:g} m route']}
        if ln.load_current_A and ln.tariff_per_kwh is not None and ln.loss_load_factor is not None:
            mat = 'a' if ln.material == 'cu' else 'b'
            try:
                with run_engine():
                    vd = L.calculate_voltage_drop(ln.size, 100.0, 1000.0, mat, 'a', 1000.0, 1.0)
            except Exception as e:  # noqa: BLE001
                bad_request(e)
            r_km = vd / 20.0
            i_run = ln.load_current_A / ln.runs
            p_kw = ln.phases * i_run ** 2 * r_km * (ln.length_m / 1000.0) * ln.runs / 1000.0
            e_kwh = p_kw * ln.loss_load_factor * ln.hours_per_year
            row.update(R_ohm_per_km=r_km, peak_loss_kW=p_kw, annual_loss_kWh=e_kwh,
                       annual_loss_cost=e_kwh * ln.tariff_per_kwh,
                       lifetime_loss_cost=e_kwh * ln.tariff_per_kwh * ln.years,
                       total_cost_of_ownership=capex + e_kwh * ln.tariff_per_kwh * ln.years)
            row['assumptions'] += [
                f'R = {r_km:.4f} ohm/km from the engine voltage-drop table (nearest tabled size, not '
                'temperature-corrected)',
                f'loss-load factor {ln.loss_load_factor} x {ln.hours_per_year:g} h/yr; no discounting',
                f'{ln.phases} loaded conductor(s) per run']
        out.append(row)
    return {'currency': body.currency, 'lines': out,
            'notice': 'Costs are computed only from the prices you entered. Cable-N holds no market price data.'}


# ---------------------------------------------------------------- batch helpers
@router.get('/batch/template.xlsx')
def batch_template():
    return Response(excel.feeder_template(),
                    media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': 'attachment; filename="cable-n-feeder-template.xlsx"'})


@router.post('/batch/import')
async def batch_import(request: Request, file: UploadFile = File(...)):
    rate_limit(request, 'calc', get_settings().CALC_RATE_PER_MINUTE)
    name = (file.filename or '').lower()
    if not name.endswith(('.xlsx', '.xlsm')):
        raise HTTPException(400, 'Upload an .xlsx workbook (use the template).')
    limit = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f'Workbook larger than {get_settings().MAX_UPLOAD_MB} MB')
    if not data.startswith(b'PK'):
        raise HTTPException(400, 'Not an Excel workbook.')
    try:
        feeders, problems = excel.parse_feeders(data)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, 'Could not read this workbook. Use the downloadable template.')
    return {'feeders': feeders, 'problems': problems}


def _batch_job(progress, cancelled, clean):
    from ..engine import mode2
    result = mode2.run_batch(clean['common'], clean['feeders'], clean.get('arrangement'),
                             progress=progress, cancelled=cancelled)
    result['verification_notice'] = VERIFICATION_NOTICE
    result['run_status'] = 'cancelled' if cancelled() else 'executed'
    return {'mode': 'batch', 'inputs': clean, 'result': result, 'summary': summarise('batch', clean, result),
            'engine_version': ENGINE_VERSION}


@router.post('/batch/jobs')
def batch_job(body: RunIn, request: Request):
    """Background batch run with real per-feeder progress and cancellation."""
    rate_limit(request, 'calc', get_settings().CALC_RATE_PER_MINUTE)
    try:
        clean = validate_inputs('batch', body.inputs)
        check_size('batch', clean)
        from ..engine import mode2
        common = mode2.common_to_legacy(clean['common'])
        opts = mode1.arrangement_options(common, mode1.table_key_for(common))
        if clean.get('arrangement') and clean['arrangement'] not in opts:
            raise InputRejected(f"Arrangement {clean['arrangement']} not rated; options {opts}")
    except Exception as e:  # noqa: BLE001
        bad_request(e)
    if jobs.active_count() >= get_settings().ENGINE_MAX_CONCURRENT * 2:
        raise HTTPException(503, 'The engine is busy - please retry in a few seconds.')
    return {'job_id': jobs.submit('batch', _batch_job, clean)}


@jobs_router.get('/{jid}')
def job_status(jid: str):
    j = jobs.get(jid)
    if not j:
        raise HTTPException(404, 'Job not found or expired')
    return jobs.public(j)


@jobs_router.post('/{jid}/cancel')
def job_cancel(jid: str):
    if not jobs.get(jid):
        raise HTTPException(404, 'Job not found or expired')
    return {'cancel_requested': jobs.cancel(jid)}
