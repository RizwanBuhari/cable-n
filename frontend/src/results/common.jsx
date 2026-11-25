import { useMemo, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'
import { num } from '../lib/format'
import { Icon } from '../components/icons'
import { ErrorBox, Field, Notice, Spinner, StatusBadge, Tip } from '../components/ui'

export function Metric({ label, value, unit, sub, accent, tip }) {
  return (
    <div className={`metric ${accent ? 'metric-accent' : ''}`}>
      <div className="metric-label">{label}{tip && <Tip text={tip} />}</div>
      <div className="metric-value">{value}{unit && <small>{unit}</small>}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  )
}

export function ChecksTable({ checks }) {
  if (!checks?.length) return null
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead><tr><th>Engineering check</th><th>Status</th><th>Detail</th></tr></thead>
        <tbody>
          {checks.map((c) => <tr key={c.name}><td>{c.name}</td><td><StatusBadge status={c.status} /></td><td>{c.detail}</td></tr>)}
        </tbody>
      </table>
    </div>
  )
}

export function Warnings({ warnings, title = 'Engineering warnings and assumptions' }) {
  if (!warnings?.length) return <Notice tone="good" icon={Icon.check}>No engineering warnings were raised for these inputs.</Notice>
  return (
    <div className="notice notice-warn">
      {Icon.alert}
      <div>
        <strong>{title}</strong>
        <ul>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
      </div>
    </div>
  )
}

export function RunInfo({ run, outdated, onRecalc, busy }) {
  if (!run) return null
  return outdated ? (
    <div className="outdated">
      <span>Inputs changed since this result was calculated — the result shown is OUTDATED.</span>
      <button className="btn-sm btn-sm-primary" onClick={onRecalc} disabled={busy}>{busy ? <Spinner light /> : Icon.refresh} Recalculate</button>
    </div>
  ) : (
    <div className="toolbar small muted mb-16">
      <span className="current-tag">Current result</span>
      <span>Engine {run.engine_version || run.result?.engine_version}</span>
      {run.stored && <span>· stored result from your saved calculation</span>}
      {run.result?._slimmed && <span>· bulky option lists were trimmed when saving; recalculate to see them</span>}
    </div>
  )
}

const DEFAULT_SWEEPS = {
  air_temp: [20, 25, 30, 35, 40, 45, 50, 55], soil_temp: [10, 15, 20, 25, 30, 35, 40, 45],
  soil_resistivity: [0.7, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0], duct_resistivity: [0.7, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0],
  depth: [0.5, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0], cable_length: [50, 100, 200, 300, 500, 750, 1000],
  power_factor: [0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1], voltage_drop_limit_pct: [1, 2, 3, 4, 5, 6],
  soil_rho: [0.8, 1.0, 1.2, 1.5, 2.0, 2.5], tg: [20, 25, 30, 35, 40, 45, 50], rho_e: [0.8, 1.0, 1.2, 1.5, 2.0, 2.5],
}
const SERIES = {
  single_feeder: [['derated_current', 'Iz (A)', '#CE1B28'], ['voltage_drop', 'Voltage drop (%)', '#2563eb'], ['utilisation', 'Utilisation (%)', '#1e7a34']],
  current_rating: [['min_rating', 'Lowest position rating (A)', '#CE1B28']],
  advanced_mvhv: [['governing_rating', 'Governing rating (A)', '#CE1B28'], ['max_theta', 'Max conductor temp (°C)', '#b45309']],
}

/** What-if / sensitivity: every point is a fresh engine run - nothing interpolated. */
export function SensitivityPanel({ mode, inputs, variables }) {
  const vars = Object.entries(variables || {})
  const [variable, setVariable] = useState(vars[0]?.[0] || '')
  const [values, setValues] = useState((DEFAULT_SWEEPS[vars[0]?.[0]] || []).join(', '))
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const parsed = useMemo(() => values.split(/[,\s;]+/).map(Number).filter((v) => Number.isFinite(v)), [values])
  async function go() {
    setBusy(true); setErr(null)
    try {
      setRes(await api('/calculations/sensitivity', { method: 'POST', body: { mode, inputs, variable, values: parsed } }))
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  if (!vars.length) return <p className="muted small">No sweepable variables apply to these inputs.</p>
  const ok = res?.points.filter((p) => p.ok) || []
  return (
    <div className="section-gap">
      <div className="form-grid">
        <Field label="Vary">
          <select value={variable} onChange={(e) => { setVariable(e.target.value); setValues((DEFAULT_SWEEPS[e.target.value] || []).join(', ')); setRes(null) }}>
            {vars.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </Field>
        <Field label="Values (comma separated, max 15)" wide><input value={values} onChange={(e) => setValues(e.target.value)} /></Field>
      </div>
      <div className="toolbar">
        <button className="btn-primary" onClick={go} disabled={busy || !parsed.length}>{busy ? <Spinner light /> : Icon.play} Run sweep ({parsed.length} engine runs)</button>
        <span className="small muted">Every other input stays as entered. Each point is a separate engine calculation.</span>
      </div>
      <ErrorBox error={err} />
      {res && (
        <>
          {res.warnings.map((w, i) => <Notice key={i}>{w}</Notice>)}
          {ok.length > 0 && (
            <div className="chart-card">
              <h3 className="chart-title">{res.label}</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={ok} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                  <CartesianGrid stroke="#eee" />
                  <XAxis dataKey="x" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v) => num(v, 2)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {(SERIES[mode] || []).map(([k, l, c]) => <Line key={k} type="monotone" dataKey={k} name={l} stroke={c} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />)}
                </LineChart>
              </ResponsiveContainer>
              <p className="small muted">Lines join engine results for readability only; values between points were not calculated.</p>
            </div>
          )}
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr><th className="num">{res.label}</th>{mode === 'single_feeder' && <><th>Selection</th><th className="num">Iz A</th><th className="num">VD %</th><th className="num">Util %</th><th>Governing</th></>}
                  {mode === 'current_rating' && <th className="num">Lowest rating A</th>}
                  {mode === 'advanced_mvhv' && <><th>Governing cable</th><th className="num">Rating A</th><th className="num">Max θ °C</th></>}<th>Note</th></tr>
              </thead>
              <tbody>
                {res.points.map((p) => (
                  <tr key={p.x} className={!p.ok || p.feasible === false ? 'row-fail' : ''}>
                    <td className="num">{p.x}</td>
                    {mode === 'single_feeder' && (p.ok && p.feasible ? (
                      <><td>{p.runs > 1 ? `${p.runs} × ` : ''}{p.size} mm²</td><td className="num">{num(p.derated_current, 1)}</td><td className="num">{num(p.voltage_drop, 2)}</td><td className="num">{num(p.utilisation, 0)}</td><td>{p.governing}</td></>
                    ) : <td colSpan={5}>{p.ok ? 'No feasible configuration' : '—'}</td>)}
                    {mode === 'current_rating' && <td className="num">{p.ok ? num(p.min_rating, 1) : '—'}</td>}
                    {mode === 'advanced_mvhv' && (p.ok ? <><td>{p.governing_tag}</td><td className="num">{num(p.governing_rating, 1)}</td><td className="num">{num(p.max_theta, 1)}</td></> : <td colSpan={3}>—</td>)}
                    <td className="small">{p.error || (p.outside_supported_range ? 'outside table range' : '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export function DataTable({ columns, rows, rowKey, onRow, rowClass, empty = 'Nothing to show.' }) {
  const [sort, setSort] = useState(null)
  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    const val = col.sortValue || ((r) => r[col.key])
    return [...rows].sort((a, b) => {
      const x = val(a); const y = val(b)
      const cmp = typeof x === 'number' && typeof y === 'number' ? x - y : String(x ?? '').localeCompare(String(y ?? ''), undefined, { numeric: true })
      return sort.dir * cmp
    })
  }, [rows, sort, columns])
  if (!rows.length) return <p className="muted small">{empty}</p>
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={`${c.num ? 'num' : ''} ${c.sortable === false ? '' : 'sortable'}`}
                onClick={() => c.sortable !== false && setSort((s) => ({ key: c.key, dir: s?.key === c.key ? -s.dir : 1 }))}>
                {c.label}{c.tip && <Tip text={c.tip} />}{sort?.key === c.key ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={rowKey ? rowKey(r) : i} className={`${rowClass ? rowClass(r) : ''} ${onRow ? 'row-click' : ''}`} onClick={onRow ? () => onRow(r) : undefined}>
              {columns.map((c) => <td key={c.key} className={c.num ? 'num' : ''}>{c.render ? c.render(r) : r[c.key] ?? '—'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
