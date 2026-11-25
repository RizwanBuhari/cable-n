import { useEffect, useState } from 'react'
import { useShareableCalc } from '../components/ChatPanel'
import { Icon } from '../components/icons'
import { OutputBar, TemplatePicker } from '../components/Outputs'
import { Choice, Collapsible, ErrorBox, Field, NumInput, PageHeader, Panel, Spinner, Tabs, Toggle, VerificationNotice } from '../components/ui'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useCalculator } from '../lib/useCalculator'
import AdvancedResult from '../results/AdvancedResult'
import { RunInfo } from '../results/common'
import CableEditor, { blankCable, cableFromPayload, cablePayload } from './CableEditor'

const PRESET_630 = { desig: '1x630', mat: 'CU', U: 33, f: 50, theta: 90, dc: 30.05, tcs: 1.0, ti: 8.0, tis: 0.9, rho_ins: 3.5, theta_scr: 87.5,
  cu_tape: { tt: 0.076, wt: 50, double: false }, t_bed: 1.6, rho_bed: 3.5, armour: { type: 'AWA', da: 2.5, Na: 60 }, tj: 3.0, rho_j: 3.5, insulation: 'XLPE', bonding: 'both_ends' }

function defaults() {
  return {
    standard: 'IEC', cables: [cableFromPayload(PRESET_630)], installation: 'buried', tg: null,
    buried: { rho_e: null, L: 1000, fill: 'none', trough_rho: 1.0, backfill_rho: 1.0, circuits: [{ type: 0, x: 0, formation: 'trefoil', spacing: 150 }, { type: 0, x: 600, formation: 'trefoil', spacing: 150 }] },
    duct: { rho_e: null, Do: 200, Dd: 180, rho_d: 6, thm: 60, fill: 'air', rho_fill: 1.2, n_in_duct: 3, soil_model: 'none', rho_native: null,
      banks: [{ rows: 2, cols: 2, hp: 300, vp: 300, top: 1.0, x0: 0, gap: 1.0 }], bank_map: {}, layers: [], positions: [{ bank: 1, row: 1, col: 1, type: 0, load: null }, { bank: 1, row: 1, col: 2, type: 0, load: null }] },
    air: { circuits: [{ type: 0, formation: 'trefoil', spacing: 150 }], has_ducts: false, ducts: { Do: 160, Dd: 140, rho_d: 3.5, n_in_duct: 3, filled: false, rho_fill: 1.2, thm: 60 },
      has_trough: false, trough: { w: 1.0, h: 0.6 }, h_factor: 1.0, has_solar: false, solar: { sigma: 0.4, H: 1000 } },
    Lroute: 1000, rho_earth: 100, t_sc: 1.0, If_sc: 31.5, emergency: false, theta_em: 105,
  }
}

function payloadOf(i) {
  const p = { standard: i.standard, cables: i.cables.map(cablePayload), installation: i.installation, Lroute: i.Lroute, rho_earth: i.rho_earth, t_sc: i.t_sc, If_sc: i.If_sc }
  if (i.tg !== null && i.tg !== undefined) p.tg = i.tg
  const strip = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== null && v !== undefined))
  if (i.installation === 'buried') {
    const b = i.buried
    p.buried = strip({ rho_e: b.rho_e, L: b.L, circuits: b.circuits.map((c) => strip({ type: c.type, x: c.x, formation: c.formation, spacing: c.formation === 'flat_spaced' ? c.spacing : null })) })
    if (b.fill === 'trough') p.buried.trough_rho = b.trough_rho
    if (b.fill === 'backfill') p.buried.backfill_rho = b.backfill_rho
    p.emergency = !!i.emergency
    if (i.emergency) p.theta_em = i.theta_em
  } else if (i.installation === 'duct') {
    const d = i.duct
    p.duct = strip({ rho_e: d.rho_e, Do: d.Do, Dd: d.Dd, rho_d: d.rho_d, thm: d.thm, fill: d.fill, rho_fill: d.fill === 'filled' ? d.rho_fill : null, n_in_duct: d.n_in_duct,
      soil_model: d.soil_model, rho_native: d.banks.length > 1 ? d.rho_native : null,
      banks: d.banks.map((b, n) => strip({ rows: b.rows, cols: b.cols, hp: b.hp, vp: b.rows > 1 ? b.vp : null, top: b.top, x0: n === 0 ? b.x0 : null, gap: n > 0 ? b.gap : null })),
      positions: d.positions.filter((q) => { const b = d.banks[q.bank - 1]; return b && q.row <= b.rows && q.col <= b.cols }).map((q) => strip({ bank: q.bank, row: q.row, col: q.col, type: q.type, load: q.load })) })
    if (d.soil_model === 'bank') p.duct.bank_map = Object.fromEntries(d.banks.map((_, n) => [String(n + 1), strip(d.bank_map[n + 1] || { Nl: 3, LG: 1150, xb: 600, yb: 800, rc: 1.0 })]))
    if (d.soil_model === 'layers') p.duct.layers = d.layers
  } else {
    const a = i.air
    p.air = { circuits: a.circuits.map((c) => strip({ type: c.type, formation: c.formation, spacing: c.formation === 'flat_spaced' ? c.spacing : null })), h_factor: a.h_factor }
    if (a.has_ducts) p.air.ducts = strip({ ...a.ducts, rho_fill: a.ducts.filled ? a.ducts.rho_fill : null })
    if (a.has_trough) p.air.trough = a.trough
    if (a.has_solar) p.air.solar = a.solar
  }
  return p
}

function CircuitTable({ circuits, cables, onChange, showX }) {
  const upd = (n, patch) => onChange(circuits.map((c, k) => (k === n ? { ...c, ...patch } : c)))
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead><tr><th>Circuit</th><th>Cable type</th>{showX && <th>Centre x (mm)</th>}<th>Formation</th><th>Spacing (mm)</th><th></th></tr></thead>
        <tbody>
          {circuits.map((c, n) => {
            const single = String(cables[c.type]?.desig || '').trim().startsWith('1')
            return (
              <tr key={n}>
                <td>C{n + 1}</td>
                <td><select className="cell-input" value={c.type} onChange={(e) => upd(n, { type: Number(e.target.value) })}>{cables.map((cb, k) => <option key={k} value={k}>{k + 1}: {cb.desig}</option>)}</select></td>
                {showX && <td><NumInput className="cell-input" value={c.x} onChange={(v) => upd(n, { x: v })} /></td>}
                <td>{single ? <select className="cell-input" value={c.formation} onChange={(e) => upd(n, { formation: e.target.value })}><option value="trefoil">Trefoil</option><option value="flat_touching">Flat touching</option><option value="flat_spaced">Flat spaced</option></select> : <span className="muted small">3-core cable</span>}</td>
                <td>{single && c.formation === 'flat_spaced' ? <NumInput className="cell-input" value={c.spacing} onChange={(v) => upd(n, { spacing: v })} /> : '—'}</td>
                <td><button className="table-row-delete" onClick={() => onChange(circuits.filter((_, k) => k !== n))} aria-label="Remove circuit">{Icon.trash}</button></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function fromPayload(p) {
  const d = defaults()
  const out = { ...d, standard: p.standard || 'IEC', cables: (p.cables || []).map(cableFromPayload), installation: p.installation, tg: p.tg ?? null,
    Lroute: p.Lroute ?? d.Lroute, rho_earth: p.rho_earth ?? d.rho_earth, t_sc: p.t_sc ?? d.t_sc, If_sc: p.If_sc ?? d.If_sc, emergency: !!p.emergency, theta_em: p.theta_em ?? d.theta_em }
  if (p.buried) {
    const b = p.buried
    out.buried = { ...d.buried, rho_e: b.rho_e ?? null, L: b.L, fill: b.trough_rho != null ? 'trough' : b.backfill_rho != null ? 'backfill' : 'none',
      trough_rho: b.trough_rho ?? 1.0, backfill_rho: b.backfill_rho ?? 1.0, circuits: b.circuits.map((c) => ({ formation: 'trefoil', spacing: 150, ...c })) }
  }
  if (p.duct) {
    const q = p.duct
    const bm = {}
    Object.entries(q.bank_map || {}).forEach(([k, v]) => { bm[Number(k)] = v })
    out.duct = { ...d.duct, ...q, rho_e: q.rho_e ?? null, rho_native: q.rho_native ?? null, fill: q.fill || 'air', soil_model: q.soil_model || 'none', bank_map: bm, layers: q.layers || [],
      banks: q.banks.map((b) => ({ vp: 300, x0: 0, gap: 1.0, ...b })), positions: q.positions.map((x) => ({ load: null, ...x })) }
  }
  if (p.air) {
    const a = p.air
    out.air = { ...d.air, circuits: a.circuits.map((c) => ({ formation: 'trefoil', spacing: 150, ...c })), h_factor: a.h_factor ?? 1,
      has_ducts: !!a.ducts, ducts: { ...d.air.ducts, ...(a.ducts || {}), filled: !!a.ducts?.rho_fill }, has_trough: !!a.trough, trough: a.trough || d.air.trough,
      has_solar: !!a.solar, solar: a.solar || d.air.solar }
  }
  return out
}

export default function AdvancedPage() {
  const c = useCalculator('advanced_mvhv', defaults, payloadOf, fromPayload)
  const { inputs: i, set } = c
  const [cableTab, setCableTab] = useState('0')
  const [bankTab, setBankTab] = useState(1)
  const [presets, setPresets] = useState(null)
  const { items: custom } = useStore('cables')
  useEffect(() => { api('/calculations/advanced-mvhv/presets').then(setPresets).catch(() => {}) }, [])
  useShareableCalc(c.run && !c.outdated ? { mode: 'advanced_mvhv', inputs: c.payload, label: 'MV/HV analysis' } : null)
  const std = presets?.standards?.[i.standard]
  const setSub = (k, patch) => set((x) => ({ [k]: { ...x[k], ...patch } }))
  const ci = Math.min(Number(cableTab), i.cables.length - 1)
  const libCables = (custom || []).filter((x) => x.data?.mode4_cable)

  async function calculate() {
    const r = await c.execute()
    if (r) setTimeout(() => document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }
  function addCable(payload) {
    set((x) => ({ cables: [...x.cables, payload ? cableFromPayload(payload) : blankCable()] }))
    setCableTab(String(i.cables.length))
  }
  const d = i.duct
  const db = d.banks[bankTab - 1] || d.banks[0]

  return (
    <div>
      <PageHeader icon={Icon.thermo} title="Advanced MV/HV analysis" hint="Mode 4 — IEC 60287 / 60949: thermal resistances, losses, full-coordinate mutual heating, electrical parameters, short-circuit and emergency ratings for your arrangement."
        actions={<><TemplatePicker mode="advanced_mvhv" onApply={c.loadPayload} /><button className="btn-sm" onClick={c.reset}>{Icon.refresh} New</button></>} />

      <Panel title="1. Design standard" icon={Icon.book}>
        <Choice value={i.standard} onChange={(v) => set({ standard: v })} options={['IEC', 'BS', 'IEEE', 'IS'].map((k) => ({ value: k, label: k, hint: presets?.standards?.[k]?.name?.split('(')[0] }))} />
        {std && <p className="small muted mt-8">{std.note} Defaults: {std.f} Hz, ground {std.tg_ground} °C, air {std.tg_air} °C, soil ρ {std.rho_soil} K·m/W. {i.standard === 'IEEE' && 'The engine is IEC 60287 — cross-check against an IEEE tool for US submissions.'}</p>}
      </Panel>

      <Panel title="2. Cable types" icon={Icon.cable} count={i.cables.length} className="mt-16" actions={(
        <div className="panel-actions">
          {i.cables.length < 8 && <button className="btn-sm" onClick={() => addCable()}>{Icon.plus} Blank type</button>}
          {presets && (
            <select className="btn-sm" value="" title="Replaces the cable type you are editing. Presets are illustrative, not manufacturer data."
              onChange={(e) => {
                const p = presets.presets[e.target.value]?.cable || libCables.find((x) => x.id === e.target.value)?.data.mode4_cable
                if (p) set((x) => ({ cables: x.cables.map((y, k) => (k === ci ? cableFromPayload(p) : y)) }))
              }}>
              <option value="">Load preset into type {ci + 1} (illustrative)…</option>
              {Object.entries(presets.presets).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              {libCables.map((x) => <option key={x.id} value={x.id}>My library: {x.code}</option>)}
            </select>
          )}
        </div>
      )}>
        <Tabs small value={String(ci)} onChange={setCableTab} tabs={i.cables.map((cb, k) => ({ id: String(k), label: `${k + 1}: ${cb.desig}` }))} />
        <CableEditor cable={i.cables[ci]} standard={i.standard} onChange={(cb) => set((x) => ({ cables: x.cables.map((y, k) => (k === ci ? cb : y)) }))} />
        {i.cables.length > 1 && <button className="btn-sm btn-sm-danger mt-16" onClick={() => { set((x) => ({ cables: x.cables.filter((_, k) => k !== ci) })); setCableTab('0') }}>Remove type {ci + 1}</button>}
      </Panel>

      <Panel title="3. Installation" icon={Icon.mapPin} className="mt-16">
        <Choice value={i.installation} onChange={(v) => set({ installation: v })} options={[{ value: 'buried', label: 'Direct buried' }, { value: 'duct', label: 'Duct bank(s)' }, { value: 'air', label: 'In air / trough' }]} />
        <div className="form-grid mt-16">
          <Field label="Ambient temperature" unit="°C" hint={std ? `Blank = ${i.installation === 'air' ? std.tg_air : std.tg_ground} °C (${i.standard})` : ''}><NumInput value={i.tg} onChange={(v) => set({ tg: v })} /></Field>
          {i.installation !== 'air' && <Field label="Soil / backfill ρ" unit="K·m/W" hint={std ? `Blank = ${std.rho_soil}` : ''}><NumInput value={i[i.installation].rho_e} onChange={(v) => setSub(i.installation, { rho_e: v })} /></Field>}
        </div>

        {i.installation === 'buried' && (
          <div className="form-section">
            <div className="form-grid">
              <Field label="Depth to circuit centres" unit="mm"><NumInput value={i.buried.L} onChange={(v) => setSub('buried', { L: v })} /></Field>
              <Field label="Surroundings">
                <select value={i.buried.fill} onChange={(e) => setSub('buried', { fill: e.target.value })}><option value="none">Native soil only</option><option value="backfill">Special backfill around cables</option><option value="trough">Concrete trough fill</option></select>
              </Field>
              {i.buried.fill === 'backfill' && <Field label="Backfill ρ" unit="K·m/W"><NumInput value={i.buried.backfill_rho} onChange={(v) => setSub('buried', { backfill_rho: v })} /></Field>}
              {i.buried.fill === 'trough' && <Field label="Trough fill ρ" unit="K·m/W"><NumInput value={i.buried.trough_rho} onChange={(v) => setSub('buried', { trough_rho: v })} /></Field>}
            </div>
            <h3 className="mt-16">Circuits</h3>
            <CircuitTable showX circuits={i.buried.circuits} cables={i.cables} onChange={(cs) => setSub('buried', { circuits: cs })} />
            <button className="btn-sm mt-8" onClick={() => setSub('buried', { circuits: [...i.buried.circuits, { type: 0, x: (i.buried.circuits.at(-1)?.x ?? -600) + 600, formation: 'trefoil', spacing: 150 }] })}>{Icon.plus} Add circuit</button>
          </div>
        )}

        {i.installation === 'duct' && (
          <div className="form-section">
            <div className="form-grid">
              <Field label="Duct OD" unit="mm"><NumInput value={d.Do} onChange={(v) => setSub('duct', { Do: v })} /></Field>
              <Field label="Duct ID" unit="mm"><NumInput value={d.Dd} onChange={(v) => setSub('duct', { Dd: v })} /></Field>
              <Field label="Duct wall ρ" unit="K·m/W"><NumInput value={d.rho_d} onChange={(v) => setSub('duct', { rho_d: v })} /></Field>
              <Field label="Mean medium temp in duct" unit="°C"><NumInput value={d.thm} onChange={(v) => setSub('duct', { thm: v })} /></Field>
              <Field label="Duct fill"><select value={d.fill} onChange={(e) => setSub('duct', { fill: e.target.value })}><option value="air">Air</option><option value="filled">Filled (grout/sand/bentonite)</option><option value="zero">Filled — zero air-gap resistance</option></select></Field>
              {d.fill === 'filled' && <Field label="Filling ρ" unit="K·m/W"><NumInput value={d.rho_fill} onChange={(v) => setSub('duct', { rho_fill: v })} /></Field>}
              <Field label="Single-core cables per duct"><select value={d.n_in_duct} onChange={(e) => setSub('duct', { n_in_duct: Number(e.target.value) })}><option value={3}>3 (trefoil in duct)</option><option value={2}>2</option><option value={1}>1</option></select></Field>
              {d.banks.length > 1 && <Field label="Native soil ρ between banks" unit="K·m/W" hint="Blank = same as backfill"><NumInput value={d.rho_native} onChange={(v) => setSub('duct', { rho_native: v })} /></Field>}
            </div>
            <Collapsible title="External soil model" right={<span className="chip">{{ none: 'none', bank: 'Neher / direct ρ', layers: 'layer stack' }[d.soil_model]}</span>}>
              <Choice value={d.soil_model} onChange={(v) => setSub('duct', { soil_model: v })} options={[
                { value: 'none', label: 'None', hint: 'Uniform soil ρ' }, { value: 'bank', label: 'Bank rectangle', hint: 'Neher-McGrath or a CYMCAP/FEA ρ' }, { value: 'layers', label: 'Layer stack', hint: 'Rectangles as in a CYMCAP layer table' }]} />
              {d.soil_model === 'bank' && d.banks.map((_, n) => {
                const e = d.bank_map[n + 1] || { Nl: 3, LG: 1150, xb: 600, yb: 800, rc: 1.0 }
                const upd = (p) => setSub('duct', { bank_map: { ...d.bank_map, [n + 1]: { ...e, ...p } } })
                return (
                  <div key={n} className="form-grid mt-8">
                    <Field label={`Bank ${n + 1}: effective ρ directly`} unit="K·m/W" hint="Blank = derive by Neher"><NumInput value={e.direct_rho ?? null} onChange={(v) => upd({ direct_rho: v })} /></Field>
                    {e.direct_rho == null && <>
                      <Field label="Loaded cables N"><NumInput value={e.Nl} onChange={(v) => upd({ Nl: v })} /></Field>
                      <Field label="Bank centre depth LG" unit="mm"><NumInput value={e.LG} onChange={(v) => upd({ LG: v })} /></Field>
                      <Field label="Shorter side x" unit="mm"><NumInput value={e.xb} onChange={(v) => upd({ xb: v })} /></Field>
                      <Field label="Longer side y" unit="mm"><NumInput value={e.yb} onChange={(v) => upd({ yb: v })} /></Field>
                      <Field label="Bank ρ" unit="K·m/W"><NumInput value={e.rc} onChange={(v) => upd({ rc: v })} /></Field>
                    </>}
                  </div>
                )
              })}
              {d.soil_model === 'layers' && (
                <>
                  <p className="small muted">Y measured down from grade; metres.</p>
                  {d.layers.map((ly, n) => (
                    <div key={n} className="form-grid mt-8">
                      {['X', 'Y', 'W', 'H', 'rho'].map((k) => <Field key={k} label={`L${n + 1} ${k === 'rho' ? 'ρ' : k}`}><NumInput value={ly[k]} onChange={(v) => setSub('duct', { layers: d.layers.map((y, m) => (m === n ? { ...y, [k]: v } : y)) })} /></Field>)}
                      <button className="btn-sm btn-sm-danger" onClick={() => setSub('duct', { layers: d.layers.filter((_, m) => m !== n) })}>Remove</button>
                    </div>
                  ))}
                  <button className="btn-sm mt-8" onClick={() => setSub('duct', { layers: [...d.layers, { X: 0, Y: 1.0, W: 1.0, H: 0.6, rho: 1.0 }] })}>{Icon.plus} Add layer</button>
                </>
              )}
            </Collapsible>
            <h3 className="mt-16">Banks and positions</h3>
            <Tabs small value={String(bankTab)} onChange={(v) => setBankTab(Number(v))} tabs={[...d.banks.map((_, n) => ({ id: String(n + 1), label: `Bank ${n + 1}`, badge: d.positions.filter((q) => q.bank === n + 1).length }))]} />
            {db && (
              <>
                <div className="form-grid">
                  <Field label="Rows"><NumInput value={db.rows} step={1} onChange={(v) => setSub('duct', { banks: d.banks.map((b, n) => (n === bankTab - 1 ? { ...b, rows: v } : b)) })} /></Field>
                  <Field label="Columns"><NumInput value={db.cols} step={1} onChange={(v) => setSub('duct', { banks: d.banks.map((b, n) => (n === bankTab - 1 ? { ...b, cols: v } : b)) })} /></Field>
                  <Field label="Horizontal pitch" unit="mm"><NumInput value={db.hp} onChange={(v) => setSub('duct', { banks: d.banks.map((b, n) => (n === bankTab - 1 ? { ...b, hp: v } : b)) })} /></Field>
                  {db.rows > 1 && <Field label="Vertical pitch" unit="mm"><NumInput value={db.vp} onChange={(v) => setSub('duct', { banks: d.banks.map((b, n) => (n === bankTab - 1 ? { ...b, vp: v } : b)) })} /></Field>}
                  <Field label="Depth to top row" unit="m"><NumInput value={db.top} onChange={(v) => setSub('duct', { banks: d.banks.map((b, n) => (n === bankTab - 1 ? { ...b, top: v } : b)) })} /></Field>
                  {bankTab === 1 ? <Field label="x of left column" unit="mm"><NumInput value={db.x0} onChange={(v) => setSub('duct', { banks: d.banks.map((b, n) => (n === 0 ? { ...b, x0: v } : b)) })} /></Field>
                    : <Field label={`Clear gap from bank ${bankTab - 1}`} unit="m"><NumInput value={db.gap} onChange={(v) => setSub('duct', { banks: d.banks.map((b, n) => (n === bankTab - 1 ? { ...b, gap: v } : b)) })} /></Field>}
                </div>
                <div className="bank-grid mt-16" style={{ gridTemplateColumns: `repeat(${Math.min(db.cols || 1, 12)}, minmax(70px, 1fr))` }}>
                  {Array.from({ length: (db.rows || 1) * (db.cols || 1) }, (_, k) => {
                    const r = Math.floor(k / db.cols) + 1
                    const col = (k % db.cols) + 1
                    const q = d.positions.find((x) => x.bank === bankTab && x.row === r && x.col === col)
                    const setQ = (patch) => setSub('duct', { positions: patch === null ? d.positions.filter((x) => x !== q) : q ? d.positions.map((x) => (x === q ? { ...x, ...patch } : x)) : [...d.positions, { bank: bankTab, row: r, col, type: 0, load: null, ...patch }] })
                    return (
                      <div key={k} className={`bank-cell ${q ? 'filled' : ''}`} style={{ cursor: 'default' }}>
                        <select className="cell-input" value={q ? q.type : ''} onChange={(e) => setQ(e.target.value === '' ? null : { type: Number(e.target.value) })} aria-label={`R${r} C${col}`}>
                          <option value="">empty</option>
                          {i.cables.map((cb, n) => <option key={n} value={n}>{cb.desig}</option>)}
                        </select>
                        {q && <NumInput className="cell-input" placeholder="load A (auto)" value={q.load} onChange={(v) => setQ({ load: v })} />}
                      </div>
                    )
                  })}
                </div>
                <p className="small muted">Leave the load blank to auto-rate a cable; enter an operating load to get its running temperature instead.</p>
              </>
            )}
            <div className="row-actions">
              {d.banks.length < 6 && <button className="btn-sm" onClick={() => { setSub('duct', { banks: [...d.banks, { rows: 1, cols: 2, hp: 300, vp: 300, top: 1.0, gap: 1.0 }] }); setBankTab(d.banks.length + 1) }}>{Icon.plus} Add bank</button>}
              {d.banks.length > 1 && <button className="btn-sm btn-sm-danger" onClick={() => { setSub('duct', { banks: d.banks.filter((_, n) => n !== bankTab - 1), positions: d.positions.filter((q) => q.bank !== bankTab).map((q) => (q.bank > bankTab ? { ...q, bank: q.bank - 1 } : q)) }); setBankTab(1) }}>Remove bank {bankTab}</button>}
            </div>
          </div>
        )}

        {i.installation === 'air' && (
          <div className="form-section">
            <h3>Circuits</h3>
            <CircuitTable circuits={i.air.circuits} cables={i.cables} onChange={(cs) => setSub('air', { circuits: cs })} />
            <button className="btn-sm mt-8" onClick={() => setSub('air', { circuits: [...i.air.circuits, { type: 0, formation: 'trefoil', spacing: 150 }] })}>{Icon.plus} Add circuit</button>
            <div className="mt-16"><Toggle checked={i.air.has_ducts} onChange={(v) => setSub('air', { has_ducts: v })} label="Cables inside ducts (in air / in a trough)" /></div>
            {i.air.has_ducts && (
              <div className="form-grid mt-8">
                {[['Do', 'Duct OD', 'mm'], ['Dd', 'Duct ID', 'mm'], ['rho_d', 'Wall ρ', 'K·m/W'], ['n_in_duct', 'Cables per duct', ''], ['thm', 'Mean medium temp', '°C']].map(([k, l, u]) => (
                  <Field key={k} label={l} unit={u}><NumInput value={i.air.ducts[k]} onChange={(v) => setSub('air', { ducts: { ...i.air.ducts, [k]: v } })} /></Field>
                ))}
                <label className="inline-check"><input type="checkbox" checked={i.air.ducts.filled} onChange={(e) => setSub('air', { ducts: { ...i.air.ducts, filled: e.target.checked } })} /> Filled ducts</label>
                {i.air.ducts.filled && <Field label="Filling ρ" unit="K·m/W"><NumInput value={i.air.ducts.rho_fill} onChange={(v) => setSub('air', { ducts: { ...i.air.ducts, rho_fill: v } })} /></Field>}
              </div>
            )}
            <div className="mt-8"><Toggle checked={i.air.has_trough} onChange={(v) => setSub('air', { has_trough: v })} label="Unfilled (air) trough — IEC 60287-2-1 §4.1.3" /></div>
            {i.air.has_trough && <div className="form-grid mt-8"><Field label="Internal width" unit="m"><NumInput value={i.air.trough.w} onChange={(v) => setSub('air', { trough: { ...i.air.trough, w: v } })} /></Field><Field label="Internal height" unit="m"><NumInput value={i.air.trough.h} onChange={(v) => setSub('air', { trough: { ...i.air.trough, h: v } })} /></Field></div>}
            <div className="form-grid mt-8"><Field label="h multiplier" hint="h_CYMCAP / h_IEC for stacked groups; 1.0 if unknown"><NumInput value={i.air.h_factor} onChange={(v) => setSub('air', { h_factor: v })} /></Field></div>
            <div className="mt-8"><Toggle checked={i.air.has_solar} onChange={(v) => setSub('air', { has_solar: v })} label="Directly exposed to solar radiation (indicative)" /></div>
            {i.air.has_solar && <div className="form-grid mt-8"><Field label="Absorption σ"><NumInput value={i.air.solar.sigma} onChange={(v) => setSub('air', { solar: { ...i.air.solar, sigma: v } })} /></Field><Field label="Intensity H" unit="W/m²"><NumInput value={i.air.solar.H} onChange={(v) => setSub('air', { solar: { ...i.air.solar, H: v } })} /></Field></div>}
          </div>
        )}
      </Panel>

      <Panel title="4. Electrical study" icon={Icon.settings} className="mt-16">
        <div className="form-grid">
          <Field label="Route length (induced voltage)" unit="m"><NumInput value={i.Lroute} onChange={(v) => set({ Lroute: v })} /></Field>
          <Field label="Earth resistivity (sequence Z0)" unit="Ω·m"><NumInput value={i.rho_earth} onChange={(v) => set({ rho_earth: v })} /></Field>
          <Field label="Short-circuit duration" unit="s"><NumInput value={i.t_sc} onChange={(v) => set({ t_sc: v })} /></Field>
          <Field label="Earth-fault level (withstand check)" unit="kA"><NumInput value={i.If_sc} onChange={(v) => set({ If_sc: v })} /></Field>
        </div>
        {i.installation === 'buried' && (
          <>
            <div className="mt-16"><Toggle checked={i.emergency} onChange={(v) => set({ emergency: v })} label="Emergency / transient rating (IEC 60853-2)" /></div>
            {i.emergency && <div className="form-grid mt-8"><Field label="Emergency conductor temperature" unit="°C"><NumInput value={i.theta_em} onChange={(v) => set({ theta_em: v })} /></Field></div>}
          </>
        )}
        <div className="toolbar mt-16"><span className="spacer" /><button className="btn-primary" onClick={calculate} disabled={c.busy}>{c.busy ? <Spinner light /> : Icon.play} Run full analysis</button></div>
      </Panel>

      <ErrorBox error={c.error} />
      {c.run && (
        <div id="results" className="mt-16">
          <h2 className="section-title">Results</h2>
          <RunInfo run={c.run} outdated={c.outdated} onRecalc={calculate} busy={c.busy} />
          <AdvancedResult inputs={c.payload} result={c.run.result}
            onMoveCircuit={i.installation === 'buried' ? (name, x) => {
              const n = Number(name.replace('C', '')) - 1
              set((s) => ({ buried: { ...s.buried, circuits: s.buried.circuits.map((cc, k) => (k === n ? { ...cc, x } : cc)) } }))
            } : undefined} />
          <div className="mt-16"><VerificationNotice /></div>
          <div className="sticky-actions"><OutputBar mode="advanced_mvhv" inputs={c.payload} run={c.run} outdated={c.outdated} saved={c.saved} onSaved={c.setSaved} /></div>
        </div>
      )}
    </div>
  )
}
