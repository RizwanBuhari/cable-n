"""Typed request models. Bounds mirror the limits the original program
enforces at its prompts (get_valid_float min/max), plus cross-field checks
that replace the conditional questions of the terminal dialogue."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

Fin = dict(allow_inf_nan=False)


class _M(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SingleFeederIn(_M):
    voltage: float = Field(gt=0, ge=1, **Fin)
    voltage_drop_limit_pct: float = Field(ge=0, le=100, **Fin)
    power_factor: float = Field(ge=0, le=1, **Fin)
    phase: Literal['single', 'three']
    load_mode: Literal['current', 'power']
    current: Optional[float] = Field(None, gt=0, **Fin)
    power: Optional[float] = Field(None, gt=0, **Fin)
    power_unit: Optional[Literal['KW', 'KVA', 'MW', 'MVA', 'kW', 'kVA']] = None
    insulation: Literal['xlpe', 'pvc'] = 'xlpe'
    core_type: Literal['1C', '3C']
    armored: bool
    material: Literal['cu', 'al']
    installation: Literal['buried', 'duct', 'air']
    soil_resistivity: Optional[float] = Field(None, ge=0.1, **Fin)
    duct_resistivity: Optional[float] = Field(None, ge=0.1, **Fin)
    soil_temp: Optional[float] = Field(None, ge=-50, le=90, **Fin)
    depth: Optional[float] = Field(None, ge=0.1, le=3.0, **Fin)
    air_temp: Optional[float] = Field(None, ge=-50, le=90, **Fin)
    cable_length: float = Field(ge=0.1, **Fin)
    arrangement: Optional[str] = None
    sc_check: bool = False
    fault_kA: Optional[float] = Field(None, ge=0.01, **Fin)
    fault_time: Optional[float] = Field(None, ge=0.01, le=5.0, **Fin)
    fault_share: Literal['equal', 'full'] = 'equal'

    @model_validator(mode='after')
    def _conditional(self):
        if self.load_mode == 'current' and self.current is None:
            raise ValueError('Load current is required when the load is entered as current.')
        if self.load_mode == 'power' and (self.power is None or self.power_unit is None):
            raise ValueError('Power value and unit are required when the load is entered as power.')
        if self.installation == 'buried' and None in (self.soil_resistivity, self.soil_temp, self.depth):
            raise ValueError('Direct buried needs soil resistivity, soil temperature and depth.')
        if self.installation == 'duct' and None in (self.duct_resistivity, self.soil_temp, self.depth):
            raise ValueError('Duct installation needs duct resistivity, soil temperature and depth.')
        if self.installation == 'air' and self.air_temp is None:
            raise ValueError('Air installation needs the ambient air temperature.')
        if self.sc_check and None in (self.fault_kA, self.fault_time):
            raise ValueError('Short-circuit check needs the fault level and clearing time.')
        if self.power_unit:
            self.power_unit = self.power_unit.upper()
        return self


class BatchCommonIn(_M):
    voltage: float = Field(ge=1, **Fin)
    phase: Literal['single', 'three']
    voltage_drop_limit_pct: float = Field(ge=0, le=100, **Fin)
    power_factor: float = Field(ge=0, le=1, **Fin)
    core_type: Literal['1C', '3C']
    armored: bool
    material: Literal['cu', 'al']
    installation: Literal['buried', 'duct', 'air']
    soil_resistivity: Optional[float] = Field(None, ge=0.1, **Fin)
    duct_resistivity: Optional[float] = Field(None, ge=0.1, **Fin)
    soil_temp: Optional[float] = Field(None, ge=-50, le=90, **Fin)
    depth: Optional[float] = Field(None, ge=0.1, le=3.0, **Fin)
    air_temp: Optional[float] = Field(None, ge=-50, le=90, **Fin)
    sc_check: bool = False
    fault_kA: Optional[float] = Field(None, ge=0.01, **Fin)
    fault_time: Optional[float] = Field(None, ge=0.01, le=5.0, **Fin)

    @model_validator(mode='after')
    def _conditional(self):
        if self.installation == 'buried' and None in (self.soil_resistivity, self.soil_temp, self.depth):
            raise ValueError('Direct buried needs soil resistivity, soil temperature and depth.')
        if self.installation == 'duct' and None in (self.duct_resistivity, self.soil_temp, self.depth):
            raise ValueError('Duct installation needs duct resistivity, soil temperature and depth.')
        if self.installation == 'air' and self.air_temp is None:
            raise ValueError('Air installation needs the ambient air temperature.')
        if self.sc_check and None in (self.fault_kA, self.fault_time):
            raise ValueError('Short-circuit check needs the fault level and clearing time.')
        return self


class FeederIn(BaseModel):
    """Row-level validation happens in the engine adapter, so one bad row
    never blocks the valid ones - hence loose typing here."""
    model_config = ConfigDict(extra='ignore')
    tag: Optional[str] = None
    name: Optional[str] = None
    load_mode: Literal['current', 'power'] = 'current'
    current: Optional[float] = None
    power: Optional[float] = None
    power_unit: Optional[str] = None
    cable_length: Optional[float] = None
    power_factor: Optional[float] = None
    voltage_drop_limit_pct: Optional[float] = None


class BatchIn(_M):
    common: BatchCommonIn
    feeders: list[FeederIn] = Field(min_length=1, max_length=500)
    arrangement: Optional[str] = None


class Mode3Position(_M):
    row: int
    col: int
    desig: str
    load: Optional[float] = Field(None, ge=0, **Fin)


class Mode3Bank(_M):
    rows: int = Field(ge=1, le=6)
    cols: int = Field(ge=1, le=12)
    h_pitch: float = Field(ge=50, le=2000, **Fin)
    v_pitch: Optional[float] = Field(None, **Fin)
    top_depth: float = Field(ge=0.1, le=3.0, **Fin)
    positions: list[Mode3Position] = []
    circuits: Optional[int] = Field(None, ge=0, le=24)


class CurrentRatingIn(_M):
    installation: Literal['duct', 'buried']
    soil_rho: float = Field(ge=0.1, **Fin)
    soil_temp: float = Field(ge=-50, le=90, **Fin)
    backfill_rho: Optional[float] = Field(None, ge=0.1, **Fin)
    rho_choice: Literal['worst', 'native', 'envelope'] = 'worst'
    armored: bool
    material: Literal['cu', 'al']
    banks: list[Mode3Bank] = Field(min_length=1, max_length=3)
    gaps: list[float] = []
    interbank_override: Optional[float] = Field(None, ge=0, le=1, **Fin)


class AdvancedIn(BaseModel):
    """Mode 4 request. Nested structures are validated field-by-field in the
    engine adapter (app/engine/mode4.py) with the original prompt bounds."""
    model_config = ConfigDict(extra='ignore')
    standard: Literal['IEC', 'BS', 'IEEE', 'IS'] = 'IEC'
    cables: list[dict] = Field(min_length=1, max_length=8)
    installation: Literal['buried', 'duct', 'air']
    tg: Optional[float] = None
    air: Optional[dict] = None
    duct: Optional[dict] = None
    buried: Optional[dict] = None
    Lroute: float = Field(1000, ge=1, le=100000, **Fin)
    rho_earth: float = Field(100, ge=1, le=10000, **Fin)
    t_sc: float = Field(1.0, ge=0.1, le=5, **Fin)
    If_sc: float = Field(31.5, ge=0.1, le=100, **Fin)
    emergency: bool = False
    theta_em: float = Field(105, ge=90, le=160, **Fin)


class CableDefIn(BaseModel):
    model_config = ConfigDict(extra='ignore')
    cable: dict
    standard: Literal['IEC', 'BS', 'IEEE', 'IS'] = 'IEC'
