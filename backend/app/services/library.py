"""Built-in cable library records, generated from the engine's own tables.

Nothing is retyped: ampacities come from base_current_tables, R and X are
recovered by calling the engine's calculate_voltage_drop() (single-phase,
1 km, pf = 1 for R and pf = 0 for X: Vd% = 2 I z / V x 100), and DC
resistances for Mode 4 come from IEC_R0_20C. These records are GENERIC
TABLE DATA from the calculation program - not any manufacturer's product data.
"""
from functools import lru_cache

from ..engine import legacy_engine as L
from ..engine.mode4 import PRESETS
from ..engine.runtime import run_engine

SOURCE = 'Built-in table of cable_sizing_FINAL.py (90 C XLPE base ratings, IEC 60502 basis)'


def _rx(size, material):
    with run_engine():
        vd_r = L.calculate_voltage_drop(size, 100.0, 1000.0, material, 'a', 1000.0, 1.0)
        vd_x = L.calculate_voltage_drop(size, 100.0, 1000.0, material, 'a', 1000.0, 0.0)
    return vd_r * 1000.0 / (200 * 100.0), vd_x * 1000.0 / (200 * 100.0)


def builtin_records():
    """Generic engine-table records + illustrative Mode 4 presets."""
    recs = []
    for tk, arrs in L.base_current_tables.items():
        mat, arm, core = tk.split('_')
        sizes = sorted({s for a in arrs.values() for s in a}, key=float)
        for size in sizes:
            r, x = _rx(size, 'a' if mat == 'CU' else 'b')
            ratings = {L.ARRANGEMENT_LABELS.get(a, a) + f' [{a}]': arrs[a].get(size) for a in arrs}
            recs.append(dict(
                code=f"{tk}-{size}", source_kind='builtin', cable_type='LV/MV power cable (generic)',
                material=mat, size_mm2=float(size), cores=1 if core == 'SINGLE' else 3, insulation='XLPE',
                armour='armoured' if arm == 'ARMOURED' else 'unarmoured', voltage_kv=None,
                data={'table_key': tk, 'base_ratings_A': ratings, 'R_ohm_per_km': r, 'X_ohm_per_km': x,
                      'R0_20C_ohm_per_km': L.IEC_R0_20C[mat].get(int(size)),
                      'max_conductor_temp_C': L.CABLE_MAX_TEMP,
                      'notes': 'R and X are the engine voltage-drop table values (nearest-size lookup).'},
                data_source=SOURCE, revision='engine', review_status='approved'))
    for key, p in PRESETS.items():
        c = p['cable']
        recs.append(dict(
            code=f'PRESET-{key}', source_kind='preset', cable_type='MV/HV cable definition (Mode 4)',
            material=c['mat'], size_mm2=float(c['desig'].split('x')[1]), cores=int(c['desig'][0]),
            insulation=c.get('insulation', 'XLPE'), armour=(c.get('armour') or {}).get('type', ''),
            voltage_kv=c['U'], data={'mode4_cable': c},
            data_source='Illustrative starting point derived from reference cables quoted in the source '
                        'program. NOT manufacturer data - replace with datasheet values.',
            revision='A', review_status='unreviewed'))
    return recs


@lru_cache(maxsize=1)
def records() -> tuple:
    """Built-in records with stable ids (cached: the tables never change at runtime)."""
    out = []
    for i, r in enumerate(builtin_records(), 1):
        out.append(dict(r, id=i))
    return tuple(out)
