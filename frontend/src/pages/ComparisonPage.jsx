import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Icon } from '../components/icons'
import { EmptyState, ErrorBox, Field, Notice, NumInput, PageHeader, Spinner, StatusBadge, Tabs } from '../components/ui'
import { api } from '../lib/api'
import { MODE_LABEL, num } from '../lib/format'
import { useStore } from '../lib/store'
import { SensitivityPanel } from '../results/common'
import { SF_SWEEP } from '../results/SingleFeederResult'

function metrics(c) {
  const r = c.result || {}
  if (c.mode === 'single_feeder') {
    const rec = r.single?.recommended || (r.best_by_spacing || []).slice().sort((a, b) => a.runs - b.runs || a.size - b.size)[0]
    return rec ? { size: `${rec.runs > 1 ? `${rec.runs} × ` : ''}${rec.size} mm²`, material: c.inputs.material?.toUpperCase(), runs: rec.runs, iz: rec.derated_current, vd: rec.voltage_drop, util: rec.utilisation, sc: rec.sc_status, isc: rec.short_circuit, governing: r.single?.governing || rec.governing, length: c.inputs.cable_length, spacing: rec.spacing } : { size: 'no solution' }
  }
  if (c.mode === 'advanced_mvhv') {
    const pl = r.placed || []
    const loss = pl.reduce((s, p) => s + (p.n || 1) * ((p.I ** 2) * p.R / 1000 * (1 + (p.lam1 || 0) + (p.lam2 || 0)) + (p.Wd || 0)), 0)
    return { size: (r.cables || []).map((x) => x.desig).join(', '), material: r.cables?.[0]?.mat, iz: r.governing?.I, governing: r.governing?.tag, theta: Math.max(...pl.map((p) => p.theta_op)), losses: loss, sc: (r.reports || []).every((x) => x.short_circuit.adequate) ? 'PASS' : 'REVIEW' }
  }
  if (c.mode === 'current_rating') return { iz: r.summary?.min_rating, governing: 'lowest position', util: Math.max(0, ...(r.positions || []).map((p) => p.util || 0)), sc: r.summary?.overload ? 'OVERLOAD' : 'OK', material: c.inputs.material?.toUpperCase() }
  return { size: `${r.summary?.calculated ?? 0} feeders`, governing: `${r.summary?.no_solution ?? 0} no solution` }
}

const ROWS = [['Mode', (c) => MODE_LABEL[c.mode]], ['Scenario', (c) => c.scenario], ['Cable', (c, m) => m.size], ['Material', (c, m) => m.material], ['Parallel runs', (c, m) => m.runs],
  ['Rating Iz (A)', (c, m) => num(m.iz, 1), 'iz', 'max'], ['Voltage drop (%)', (c, m) => num(m.vd, 2), 'vd', 'min'], ['Utilisation (%)', (c, m) => num(m.util, 0), 'util'],
  ['Short circuit', (c, m) => (m.sc ? <StatusBadge status={m.sc} /> : '—')], ['Isc withstand (kA)', (c, m) => num(m.isc, 2), 'isc', 'max'],
  ['Max conductor temp (°C)', (c, m) => num(m.theta, 1), 'theta', 'min'], ['Losses (W/m, all cables)', (c, m) => num(m.losses, 1), 'losses', 'min'],
  ['Group spacing', (c, m) => m.spacing], ['Route length (m)', (c, m) => m.length], ['Governing', (c, m) => m.governing]]

export default function ComparisonPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || 'compare'
  const { items: calcs } = useStore('calculations')
  const [ids, setIds] = useState(() => (params.get('ids') || '').split(',').filter(Boolean))
  const chosen = (calcs || []).filter((c) => ids.includes(c.id) && c.result)
  const rows = chosen.map((c) => ({ c, m: metrics(c) }))
  const [base, setBase] = useState('')
  const baseCalc = (calcs || []).find((c) => c.id === base)

  return (
    <div>
      <PageHeader icon={Icon.compare} title="Comparison" hint="Compare saved options side by side, sweep inputs through the engine, and estimate cost from your own prices." />
      <Tabs value={tab} onChange={(t) => setParams({ tab: t })} tabs={[{ id: 'compare', label: 'Compare saved' }, { id: 'sensitivity', label: 'Sensitivity' }, { id: 'cost', label: 'Cost estimate' }]} />
      {tab === 'compare' && (
        <>
          {!calcs?.length ? <EmptyState icon={Icon.save}>Save two or more calculations first (any calculator → Save to browser).</EmptyState> : (
            <>
              <div className="pill-row mb-16">
                {calcs.filter((c) => c.result).map((c) => (
                  <label key={c.id} className="chip" style={{ cursor: 'pointer', background: ids.includes(c.id) ? 'var(--brand-red-soft)' : undefined }}>
                    <input type="checkbox" checked={ids.includes(c.id)} onChange={(e) => setIds(e.target.checked ? [...ids, c.id].slice(-6) : ids.filter((x) => x !== c.id))} /> {c.title} · {c.scenario}
                  </label>
                ))}
              </div>
              {rows.length >= 1 && (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead><tr><th>Metric</th>{rows.map(({ c }) => <th key={c.id}><Link className="table-link" to={`/calculators/saved/${c.id}`}>{c.title}</Link></th>)}</tr></thead>
                    <tbody>
                      {ROWS.map(([l, fn, key, best]) => {
                        const vals = rows.map(({ m }) => m[key]).filter((v) => typeof v === 'number')
                        if (rows.every(({ c, m }) => { const v = fn(c, m); return v === undefined || v === '—' || v === null })) return null
                        const target = best && vals.length > 1 ? (best === 'max' ? Math.max(...vals) : Math.min(...vals)) : null
                        return <tr key={l}><th>{l}</th>{rows.map(({ c, m }) => <td key={c.id} style={target !== null && m[key] === target ? { fontWeight: 800, color: 'var(--pass)' } : undefined}>{fn(c, m) ?? '—'}</td>)}</tr>
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="small muted">Green marks the best value of that single metric only. Trade-offs differ by project — no option is declared better overall, and cost is not considered unless you estimate it.</p>
            </>
          )}
        </>
      )}
      {tab === 'sensitivity' && (
        <div className="section-gap">
          <Field label="Base calculation (saved)">
            <select value={base} onChange={(e) => setBase(e.target.value)}><option value="">Choose…</option>{(calcs || []).filter((c) => c.mode !== 'batch').map((c) => <option key={c.id} value={c.id}>{c.title} — {MODE_LABEL[c.mode]}</option>)}</select>
          </Field>
          {baseCalc && <SensitivityPanel key={base} mode={baseCalc.mode} inputs={baseCalc.inputs} variables={baseCalc.mode === 'single_feeder' ? SF_SWEEP(baseCalc.inputs) : baseCalc.mode === 'current_rating' ? { soil_rho: 'Soil thermal resistivity (K·m/W)', soil_temp: 'Soil temperature (°C)' } : { tg: 'Ambient temperature (°C)', ...(baseCalc.inputs.installation !== 'air' ? { rho_e: 'Soil thermal resistivity (K·m/W)', depth: 'Depth to circuit centres (mm)' } : {}) }} />}
        </div>
      )}
      {tab === 'cost' && <CostEstimate calcs={calcs || []} />}
    </div>
  )
}

function CostEstimate({ calcs }) {
  const line = { label: 'Option A', size: '240', runs: 1, cables_per_run: 1, length_m: 100, cost_per_m: null, install_cost: 0, duct_cost: 0, other_cost: 0, material: 'cu', load_current_A: null, phases: 3, loss_load_factor: null, hours_per_year: 8760, tariff_per_kwh: null, years: 20 }
  const [currency, setCurrency] = useState('')
  const [lines, setLines] = useState([line])
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const sfs = useMemo(() => calcs.filter((c) => c.mode === 'single_feeder' && c.result), [calcs])
  useEffect(() => setRes(null), [lines])
  function fromCalc(id, n) {
    const c = sfs.find((x) => x.id === id); if (!c) return
    const m = metrics(c)
    const rec = c.result.single?.recommended || c.result.best_by_spacing?.[0]
    setLines(lines.map((l, k) => (k === n ? { ...l, label: c.title, size: rec?.size || l.size, runs: rec?.runs || 1, cables_per_run: c.inputs.core_type === '1C' ? 3 : 1, length_m: c.inputs.cable_length, material: c.inputs.material, load_current_A: c.result.design_current, phases: c.inputs.phase === 'single' ? 2 : 3 } : l)))
    void m
  }
  async function go() {
    setBusy(true); setErr(null)
    try { setRes(await api('/calculations/cost-estimate', { method: 'POST', body: { currency, lines: lines.map((l) => ({ ...l, cost_per_m: l.cost_per_m ?? 0 })) } })) } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const upd = (n, p) => setLines(lines.map((l, k) => (k === n ? { ...l, ...p } : l)))
  return (
    <div className="section-gap">
      <Notice tone="info">Cable-N has no market prices. Enter your own quotations; energy-loss cost needs a load current, loss-load factor and tariff.</Notice>
      <Field label="Currency label"><input value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="e.g. USD" maxLength={10} /></Field>
      {lines.map((l, n) => (
        <div key={n} className="card">
          <div className="toolbar mb-16"><strong>{l.label}</strong><span className="spacer" />
            {sfs.length > 0 && <select className="btn-sm" value="" onChange={(e) => fromCalc(e.target.value, n)}><option value="">Fill from saved single feeder…</option>{sfs.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}</select>}
            {lines.length > 1 && <button className="btn-sm btn-sm-danger" onClick={() => setLines(lines.filter((_, k) => k !== n))}>{Icon.trash}</button>}
          </div>
          <div className="form-grid">
            <Field label="Label"><input value={l.label} onChange={(e) => upd(n, { label: e.target.value })} /></Field>
            <Field label="Size" unit="mm²"><input value={l.size} onChange={(e) => upd(n, { size: e.target.value })} /></Field>
            <Field label="Material"><select value={l.material} onChange={(e) => upd(n, { material: e.target.value })}><option value="cu">Cu</option><option value="al">Al</option></select></Field>
            <Field label="Parallel runs"><NumInput value={l.runs} step={1} onChange={(v) => upd(n, { runs: v })} /></Field>
            <Field label="Cables per run" hint="3 for single-core"><NumInput value={l.cables_per_run} step={1} onChange={(v) => upd(n, { cables_per_run: v })} /></Field>
            <Field label="Route length" unit="m"><NumInput value={l.length_m} onChange={(v) => upd(n, { length_m: v })} /></Field>
            <Field label="Cable price" unit="/m"><NumInput value={l.cost_per_m} onChange={(v) => upd(n, { cost_per_m: v })} /></Field>
            <Field label="Installation cost"><NumInput value={l.install_cost} onChange={(v) => upd(n, { install_cost: v })} /></Field>
            <Field label="Duct cost"><NumInput value={l.duct_cost} onChange={(v) => upd(n, { duct_cost: v })} /></Field>
            <Field label="Other costs"><NumInput value={l.other_cost} onChange={(v) => upd(n, { other_cost: v })} /></Field>
            <Field label="Load current" unit="A"><NumInput value={l.load_current_A} onChange={(v) => upd(n, { load_current_A: v })} /></Field>
            <Field label="Loss-load factor" hint="0–1"><NumInput value={l.loss_load_factor} onChange={(v) => upd(n, { loss_load_factor: v })} /></Field>
            <Field label="Tariff" unit="/kWh"><NumInput value={l.tariff_per_kwh} onChange={(v) => upd(n, { tariff_per_kwh: v })} /></Field>
            <Field label="Years"><NumInput value={l.years} step={1} onChange={(v) => upd(n, { years: v })} /></Field>
          </div>
        </div>
      ))}
      <div className="toolbar">
        {lines.length < 6 && <button className="btn-outline" onClick={() => setLines([...lines, { ...line, label: `Option ${String.fromCharCode(65 + lines.length)}` }])}>{Icon.plus} Add option</button>}
        <button className="btn-primary" onClick={go} disabled={busy}>{busy ? <Spinner light /> : Icon.play} Estimate</button>
      </div>
      <ErrorBox error={err} />
      {res && (
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Option</th><th className="num">Cable m</th><th className="num">Capex</th><th className="num">Loss kWh/yr</th><th className="num">Loss cost/yr</th><th className="num">Lifetime total</th><th>Assumptions</th></tr></thead>
            <tbody>{res.lines.map((l) => (
              <tr key={l.label}><td>{l.label}</td><td className="num">{num(l.cable_length_total_m, 0)}</td><td className="num">{currency} {num(l.capex, 0)}</td>
                <td className="num">{num(l.annual_loss_kWh, 0)}</td><td className="num">{l.annual_loss_cost != null ? `${currency} ${num(l.annual_loss_cost, 0)}` : '—'}</td>
                <td className="num">{l.total_cost_of_ownership != null ? `${currency} ${num(l.total_cost_of_ownership, 0)}` : '—'}</td><td className="small" style={{ whiteSpace: 'normal' }}>{l.assumptions.join('; ')}</td></tr>
            ))}</tbody>
          </table>
          <p className="small muted" style={{ padding: '0 12px' }}>{res.notice}</p>
        </div>
      )}
    </div>
  )
}
