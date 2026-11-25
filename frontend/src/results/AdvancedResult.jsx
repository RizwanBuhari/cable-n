import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrangementDiagram, CableSection } from '../diagrams/Diagrams'
import { api } from '../lib/api'
import { num } from '../lib/format'
import { Collapsible, ErrorBox, KV, Notice, Spinner, StatusBadge, Tabs } from '../components/ui'
import { DataTable, Metric, SensitivityPanel, Warnings } from './common'

const T = {
  T1: 'Thermal resistance of the insulation (conductor to sheath), K·m/W',
  T2: 'Thermal resistance between sheath and armour (bedding / filler), K·m/W',
  T3: 'Thermal resistance of the outer covering (jacket), K·m/W',
  T4: 'External thermal resistance (soil, duct, air), including the cable\'s own image term, K·m/W',
  lam1: 'λ1 — sheath/screen loss as a fraction of conductor loss',
  lam2: 'λ2 — armour loss as a fraction of conductor loss',
  Wd: 'Dielectric loss per phase, W/m',
  R: 'AC resistance of the conductor at maximum operating temperature, Ω/km',
}

function Losses({ placed }) {
  const rows = placed.map((p) => {
    const n = p.n || 1
    const Wc = (p.I ** 2) * p.R / 1000
    return { ...p, Wc, Ws: Wc * (p.lam1 || 0), Wa: Wc * (p.lam2 || 0), total: n * (Wc * (1 + (p.lam1 || 0) + (p.lam2 || 0)) + (p.Wd || 0)) }
  })
  return (
    <>
      <p className="small muted">Per conductor at the cable's own rating (or entered load): W<sub>c</sub> = I²R, sheath W<sub>s</sub> = λ1·W<sub>c</sub>, armour W<sub>a</sub> = λ2·W<sub>c</sub>, dielectric W<sub>d</sub>. Total is per cable (× cores for 3-core).</p>
      <DataTable rows={rows} rowKey={(p) => p.tag} columns={[
        { key: 'tag', label: 'Position' }, { key: 'desig', label: 'Cable' },
        { key: 'I', label: 'I A', num: true, render: (p) => num(p.I, 1) },
        { key: 'Wc', label: 'Wc W/m', num: true, tip: 'Conductor Joule loss', render: (p) => num(p.Wc, 3) },
        { key: 'lam1', label: 'λ1', num: true, tip: T.lam1, render: (p) => num(p.lam1, 5) },
        { key: 'Ws', label: 'Ws W/m', num: true, render: (p) => num(p.Ws, 3) },
        { key: 'lam2', label: 'λ2', num: true, tip: T.lam2, render: (p) => num(p.lam2, 5) },
        { key: 'Wa', label: 'Wa W/m', num: true, render: (p) => num(p.Wa, 3) },
        { key: 'Wd', label: 'Wd W/m', num: true, tip: T.Wd, render: (p) => num(p.Wd, 4) },
        { key: 'total', label: 'Total W/m', num: true, render: (p) => <b>{num(p.total, 2)}</b> },
      ]} />
    </>
  )
}

export default function AdvancedResult({ inputs, result: r, onMoveCircuit }) {
  const [tab, setTab] = useState('summary')
  const [sel, setSel] = useState(r.governing.tag)
  const [iso, setIso] = useState(null)
  const [sens, setSens] = useState(null)
  const [sensErr, setSensErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const reports = useMemo(() => Object.fromEntries(r.reports.map((x) => [x.tag, x])), [r])
  const selP = r.placed.find((p) => p.tag === sel)
  const selR = reports[sel]
  const hasEm = r.reports.some((x) => x.emergency)
  const over = r.placed.filter((p) => p.over_limit)
  const scBad = r.reports.filter((x) => !x.short_circuit.adequate)
  const isoKey = JSON.stringify(inputs)
  useEffect(() => { setIso(null); setSens(null) }, [isoKey])
  useEffect(() => {
    if (tab === 'layout' && !iso && r.installation !== 'air') {
      api('/calculations/advanced-mvhv/isotherms', { method: 'POST', body: { inputs } }).then(setIso).catch(() => setIso({ available: false }))
    }
  }, [tab, iso, inputs, r.installation])
  async function loadSens() {
    setBusy(true); setSensErr(null)
    try { setSens(await api('/calculations/advanced-mvhv/sensitivity', { method: 'POST', body: { inputs } })) } catch (e) { setSensErr(e) } finally { setBusy(false) }
  }
  const sweepVars = { tg: 'Ambient temperature (°C)' }
  if (r.installation !== 'air') { sweepVars.rho_e = 'Soil thermal resistivity (K·m/W)'; sweepVars.depth = 'Depth to circuit centres (mm)' }
  if ((inputs[r.installation]?.circuits || []).some((c) => c.formation === 'flat_spaced')) sweepVars.spacing = 'Flat-spaced spacing (mm)'

  return (
    <div>
      {r.multibank_unvalidated && <Notice tone="alert"><b>Multi-bank estimate — not validated against CYMCAP.</b> Treat these ratings as engineering estimates and cross-check one case independently.</Notice>}
      <div className="result-hero mt-8">
        <Metric accent label="Governing rating" value={num(r.governing.I, 1)} unit="A" sub={`${r.governing.tag} · ${r.governing.desig}`} tip="Lowest steady-state rating in the arrangement, with every neighbour at its own rating or entered load." />
        <Metric label="Cables rated" value={r.placed.length} sub={`${r.cables.length} cable type(s)`} />
        <Metric label="Installation" value={{ buried: 'Buried', duct: 'Ducts', air: 'Air' }[r.installation]} sub={`${r.formation} · ambient ${num(r.tg, 1)} °C`} />
        <Metric label="Over temperature" value={over.length} sub={over.length ? over.map((p) => p.tag).join(', ') : 'none at the entered loads'} />
        <Metric label="Short-circuit review" value={scBad.length} sub={scBad.length ? 'metallic layers below fault level' : 'all metallic layers adequate'} />
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[
        { id: 'summary', label: 'Summary' }, { id: 'ratings', label: 'Current ratings' }, { id: 'electrical', label: 'Electrical' },
        { id: 'sequence', label: 'Sequence & induced' }, { id: 'thermal', label: 'Thermal' }, { id: 'losses', label: 'Losses' },
        { id: 'layout', label: 'Installation layout' }, { id: 'sc', label: 'Short circuit', badge: scBad.length || null, badgeTone: 'alert' },
        ...(hasEm ? [{ id: 'emergency', label: 'Emergency' }] : []), { id: 'sensitivity', label: 'Sensitivity' },
        { id: 'cables', label: 'Cable data' }, { id: 'assumptions', label: 'Assumptions', badge: r.warnings.length || null, badgeTone: 'warn' },
        { id: 'details', label: 'Calculation details' },
      ]} />

      {tab === 'summary' && (
        <div className="section-gap">
          <Warnings warnings={r.warnings} />
          <KV rows={[['Standard basis', r.standard.name], ['Ambient', `${num(r.tg, 1)} °C`], r.installation !== 'air' && ['Soil / backfill ρ used', `${num(r.rho_e, 3)} K·m/W${r.rho_native && r.rho_native !== r.rho_e ? ` · native ${num(r.rho_native, 3)}` : ''}`],
            r.duct && ['Duct OD / ID', `${r.duct[0]} / ${r.duct[1]} mm, wall ρ ${r.duct[2]}, medium ${r.duct[3]} °C${r.duct[4] ? `, filled ρ ${r.duct[4]}` : ''}`],
            r.trough && ['Unfilled trough', `${r.trough[0]} × ${r.trough[1]} m`], r.solar && ['Solar', `σ ${r.solar[0]}, H ${r.solar[1]} W/m² (indicative)`]]} />
          <div className="split">
            <ArrangementDiagram result={r} selected={sel} onSelect={setSel} />
            {selP && (
              <div className="card">
                <h3 className="mt-0">{selP.tag} — {selP.desig}</h3>
                <KV rows={[['Rating', `${num(selP.I, 1)} A`], selP.load != null && ['Entered load', `${num(selP.load, 1)} A`], ['Conductor temperature', `${num(selP.theta_op, 1)} °C (max ${selP.theta_max})`],
                  ['Position x / y', `${num(selP.x, 0)} / ${num(selP.y, 0)} mm`], ['T4', num(selP.T4, 4), T.T4], ['Mutual heating ΔT', `${num(selP.dt_int, 2)} K`],
                  ['Short circuit', selR && <StatusBadge status={selR.short_circuit.adequate ? 'ADEQUATE' : 'REVIEW'} label={`${num(selR.short_circuit.total, 1)} kA vs ${selR.short_circuit.If} kA`} />]]} />
                <p className="small muted">Click any cable in the diagram to inspect it.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'ratings' && (
        <DataTable rows={r.placed} rowKey={(p) => p.tag} rowClass={(p) => (p.over_limit ? 'row-fail' : p.tag === r.governing.tag ? 'row-rec' : '')} onRow={(p) => setSel(p.tag)} columns={[
          { key: 'tag', label: 'Position' }, { key: 'desig', label: 'Cable' },
          { key: 'x', label: 'x mm', num: true, render: (p) => num(p.x, 0) }, { key: 'y', label: 'y mm', num: true, render: (p) => num(p.y, 0) },
          { key: 'T4', label: 'T4', num: true, tip: T.T4, render: (p) => num(p.T4, 4) },
          { key: 'dt_int', label: 'ΔT int K', num: true, tip: 'Temperature rise from neighbouring cables (mutual heating)', render: (p) => num(p.dt_int, 2) },
          { key: 'I', label: 'Rating A', num: true, render: (p) => <b>{num(p.I, 1)}</b> },
          { key: 'load', label: 'Load A', num: true, render: (p) => (p.load == null ? 'auto' : num(p.load, 1)) },
          { key: 'theta_op', label: 'θ cond °C', num: true, render: (p) => num(p.theta_op, 1) },
          { key: 'over', label: 'Status', sortable: false, render: (p) => (p.over_limit ? <StatusBadge status="FAIL" label="Over limit" /> : <StatusBadge status="OK" />) },
        ]} />
      )}

      {tab === 'electrical' && (
        <DataTable rows={r.reports} rowKey={(x) => x.tag} columns={[
          { key: 'tag', label: 'Position' }, { key: 'I', label: 'I A', num: true, render: (x) => num(x.I, 1) },
          { key: 'R', label: 'R ac Ω/km', num: true, tip: T.R, render: (x) => num(x.electrical.R, 5) },
          { key: 'XL', label: 'XL Ω/km', num: true, render: (x) => num(x.electrical.XL, 5) },
          { key: 'L', label: 'L mH/km', num: true, render: (x) => num(x.electrical.L, 4) },
          { key: 'C', label: 'C µF/km', num: true, render: (x) => num(x.electrical.C, 4) },
          { key: 'Ich', label: 'Ich A/km', num: true, tip: 'Charging current', render: (x) => num(x.electrical.Ich, 3) },
          { key: 'Q', label: 'Q kvar/km', num: true, render: (x) => num(x.electrical.Q, 1) },
          { key: 'Wd', label: 'Wd W/m', num: true, tip: T.Wd, render: (x) => num(x.electrical.Wd, 4) },
          { key: 'Vcs', label: 'E cond-scr kV/mm', num: true, tip: 'Electric stress at the conductor screen', render: (x) => num(x.electrical.Vcs, 2) },
          { key: 'Vis', label: 'E ins-scr kV/mm', num: true, render: (x) => num(x.electrical.Vis, 2) },
          { key: 'Zs', label: 'Surge Z Ω', num: true, render: (x) => num(x.electrical.Zs, 1) },
          { key: 'loss', label: 'Loss kW/km', num: true, render: (x) => num(x.electrical.loss_kw_km, 2) },
        ]} />
      )}

      {tab === 'sequence' && (
        <DataTable rows={r.reports} rowKey={(x) => x.tag} columns={[
          { key: 'tag', label: 'Position' },
          { key: 'Z1', label: 'Z1 = Z2 Ω/km', render: (x) => `${num(x.sequence.Z1.re, 4)} + j${num(x.sequence.Z1.im, 4)}` },
          { key: 'Z1a', label: '|Z1|', num: true, render: (x) => num(x.sequence.Z1.abs, 4) },
          { key: 'Z0', label: 'Z0 Ω/km', render: (x) => `${num(x.sequence.Z0.re, 4)} + j${num(x.sequence.Z0.im, 4)}` },
          { key: 'Z0a', label: '|Z0|', num: true, render: (x) => num(x.sequence.Z0.abs, 4) },
          { key: 'Vt', label: 'Sheath V trefoil', num: true, tip: 'Standing voltage over the route length at this current (single-point / cross-bonded sections). Common touch limit 65 V.', render: (x) => <span style={{ color: x.induced.V_tref > 65 ? 'var(--fail)' : undefined }}>{num(x.induced.V_tref, 1)} V</span> },
          { key: 'Vo', label: 'Flat outer V', num: true, render: (x) => `${num(x.induced.V_out, 1)} V` },
          { key: 'L', label: 'Route m', num: true, render: (x) => num(x.induced.Lroute, 0) },
        ]} />
      )}

      {tab === 'thermal' && (
        <DataTable rows={r.placed} rowKey={(p) => p.tag} columns={[
          { key: 'tag', label: 'Position' }, { key: 'desig', label: 'Cable' },
          ...['T1', 'T2', 'T3', 'T4'].map((k) => ({ key: k, label: k, num: true, tip: T[k], render: (p) => num(p[k], 4) })),
          { key: 'dtheta', label: 'Δθ K', num: true, tip: 'θmax − ambient', render: (p) => num(p.dtheta, 1) },
          { key: 'dt_int', label: 'ΔT int K', num: true, render: (p) => num(p.dt_int, 2) },
          { key: 'rho_ext', label: 'ρ ext', num: true, tip: 'Effective external soil resistivity at this position (soil models)', render: (p) => num(p.rho_ext, 3) },
          { key: 'theta_op', label: 'θ °C', num: true, render: (p) => num(p.theta_op, 1) },
        ]} />
      )}

      {tab === 'losses' && <Losses placed={r.placed} />}

      {tab === 'layout' && (
        <div className="section-gap">
          <ArrangementDiagram result={r} selected={sel} onSelect={setSel} editable={!!onMoveCircuit} onMoveCircuit={onMoveCircuit} isotherms={iso} />
          {iso === null && r.installation !== 'air' && <p className="small muted"><Spinner /> Preparing indicative heat map…</p>}
          <p className="small muted">The heat map (when shown) is an indicative superposition of image sources for visualisation only — it is not an independent finite-element simulation and does not alter the ratings.</p>
        </div>
      )}

      {tab === 'sc' && (
        <div className="section-gap">
          {r.reports.map((x) => (
            <Collapsible key={x.tag} defaultOpen={!x.short_circuit.adequate} title={`${x.tag} — ${x.short_circuit.desig}`} right={<StatusBadge status={x.short_circuit.adequate ? 'ADEQUATE' : 'REVIEW'} label={x.short_circuit.adequate ? 'Adequate' : 'Review'} />}>
              <KV rows={[['Conductor withstand', `${num(x.short_circuit.Icond, 1)} kA for ${x.short_circuit.t} s`], ['Metallic layers combined', `${num(x.short_circuit.total, 1)} kA vs earth fault ${x.short_circuit.If} kA`]]} />
              <DataTable rows={x.short_circuit.rows} rowKey={(l) => l.name} columns={[
                { key: 'name', label: 'Layer' }, { key: 'matl', label: 'Material' }, { key: 'A', label: 'Area mm²', num: true, render: (l) => num(l.A, 1) },
                { key: 'share', label: 'Fault share kA', num: true, render: (l) => num(l.share, 2) },
                { key: 'Iad', label: 'Adiabatic kA', num: true, render: (l) => num(l.Iad, 2) },
                { key: 'e1', label: 'ε non-adiabatic', num: true, render: (l) => num(l.e1, 3) },
                { key: 'Inon', label: 'Withstand kA', num: true, render: (l) => num(l.Inon, 2) },
                { key: 'ok', label: 'Share OK', render: (l) => <StatusBadge status={l.ok ? 'PASS' : 'REVIEW'} /> }]} />
            </Collapsible>
          ))}
          <p className="small muted">IEC 60949 adiabatic with non-adiabatic factor; the fault is shared between parallel metallic layers by resistance.</p>
        </div>
      )}

      {tab === 'emergency' && hasEm && (() => {
        const em = r.reports.find((x) => x.tag === sel && x.emergency) || r.reports.find((x) => x.emergency)
        const data = Object.entries(em.emergency.curves).map(([t, v]) => ({ t: Number(t), ...v })).sort((a, b) => a.t - b.t)
        return (
          <div className="section-gap">
            <p className="small muted">IEC 60853-2 transient temperature rise above the pre-load steady state for {em.tag} (select another cable in the diagram to change).</p>
            <div className="chart-card">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={data}><CartesianGrid stroke="#eee" /><XAxis dataKey="t" unit=" h" tick={{ fontSize: 12 }} /><YAxis unit=" K" tick={{ fontSize: 12 }} /><Tooltip formatter={(v) => num(v, 2)} /><Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line dataKey="theta" name="θ total rise" stroke="#CE1B28" strokeWidth={2} isAnimationActive={false} />
                  <Line dataKey="theta_c" name="θc cable part" stroke="#2563eb" isAnimationActive={false} />
                  <Line dataKey="theta_e" name="θe environment part" stroke="#b45309" isAnimationActive={false} /></LineChart>
              </ResponsiveContainer>
            </div>
            <DataTable rows={data} rowKey={(d) => d.t} columns={[{ key: 't', label: 'Time h', num: true }, { key: 'theta', label: 'θ K', num: true, render: (d) => num(d.theta, 2) }, { key: 'theta_c', label: 'θc K', num: true, render: (d) => num(d.theta_c, 2) }, { key: 'alpha', label: 'α', num: true, render: (d) => num(d.alpha, 4) }, { key: 'theta_e', label: 'θe K', num: true, render: (d) => num(d.theta_e, 2) }]} />
            {em.emergency.prior_temps && <KV rows={Object.entries(em.emergency.prior_temps).map(([k, v]) => [`Steady temperature at ${k} % prior load`, `${num(v, 1)} °C`])} />}
          </div>
        )
      })()}

      {tab === 'sensitivity' && (
        <div className="section-gap">
          {r.installation !== 'air' && (
            <div className="card">
              <h3 className="mt-0">Original report sensitivity tables (governing cable)</h3>
              <p className="small muted">Single-cable sweeps without mutual heating, exactly as in the original report. The load-factor sweep uses its simplified μ scaling (indicative, not an IEC 60853 cyclic rating).</p>
              {!sens && <button className="btn-outline" onClick={loadSens} disabled={busy}>{busy ? <Spinner /> : null} Compute tables</button>}
              <ErrorBox error={sensErr} />
              {sens && (
                <div className="split">
                  {[['depth', 'Depth m'], ['rho', 'Soil ρ K·m/W'], ['load_factor', 'Load factor']].map(([k, l]) => (
                    <DataTable key={k} rows={sens[k]} rowKey={(d) => d.x} columns={[{ key: 'x', label: l, num: true }, { key: 'I', label: 'Rating A', num: true, render: (d) => num(d.I, 1) }]} />
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="card">
            <h3 className="mt-0">What-if with full mutual heating</h3>
            <SensitivityPanel mode="advanced_mvhv" inputs={inputs} variables={sweepVars} />
          </div>
        </div>
      )}

      {tab === 'cables' && (
        <div className="section-gap">
          {r.cables.map((c, k) => (
            <Collapsible key={k} defaultOpen={k === 0} title={`Type ${k + 1}: ${c.desig} ${c.mat}, ${c.U} kV`}>
              <div className="split">
                <CableSection cable={c} height={260} />
                <KV rows={[['U0', `${num(c.U0, 2)} kV`], ['f / θmax', `${c.f} Hz / ${c.theta} °C`], ['dc / Dcs / Di / Dis', `${num(c.dc, 2)} / ${num(c.Dcs, 2)} / ${num(c.Di, 2)} / ${num(c.Dis, 2)} mm`],
                  ['Over screen / De', `${num(c.D_over_screen, 2)} / ${num(c.De, 2)} mm`], ['T1 / T2 / T3', `${num(c.T1, 4)} / ${num(c.T2, 4)} / ${num(c.T3, 4)}`],
                  ['ks / kp', `${c.ks} / ${c.kp}`], ['ε / tan δ', `${c.eps} / ${c.tan_delta}`], ['Screen R hot', c.Rs_hot > 1e6 ? 'none' : `${num(c.Rs_hot, 4)} Ω/km`],
                  ['Bonding', c.bonding === 'single' ? 'Single-point / cross-bonded' : 'Both ends'],
                  ['Metallic layers', c.screen_layers.map((l) => `${l.name} ${num(l.A, 1)} mm²`).join(', ') || 'none'],
                  ['Armour', c.armour ? `${c.armour.type} ${num(c.armour.area, 1)} mm²` : 'none'],
                  c.n === 3 && ['3-core', `${c.n3_construction}${c.G_T2 ? `, G ${num(c.G_T2, 5)}` : ''}`]]} />
              </div>
            </Collapsible>
          ))}
        </div>
      )}

      {tab === 'assumptions' && (
        <div className="section-gap">
          <Warnings warnings={r.warnings} title="Engine notes and assumptions" />
          <div className="card">
            <h3 className="mt-0">Method</h3>
            <ul className="small">
              <li>Ratings per IEC 60287-1-1 / 60287-2-1 with explicit image-method mutual heating at every neighbour's actual losses (converged iteratively).</li>
              <li>Short-circuit per IEC 60949 (adiabatic with non-adiabatic factor); emergency transient per IEC 60853-2 (buried only).</li>
              <li>Standard defaults: {r.standard.name}.</li>
              <li>Validation status of this engine against its reference cases is published in the <Link className="table-link" to="/validation">Validation centre</Link>, including the cases outside tolerance.</li>
            </ul>
          </div>
        </div>
      )}

      {tab === 'details' && (
        <div className="section-gap">
          <Collapsible title="Inputs sent to the engine"><pre className="mono small" style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(inputs, null, 2)}</pre></Collapsible>
          <Collapsible title="Engine messages"><pre className="mono small" style={{ whiteSpace: 'pre-wrap' }}>{(r.engine_messages || []).join('\n') || '(none)'}</pre></Collapsible>
          <Collapsible title="Full result (JSON)"><pre className="mono small" style={{ whiteSpace: 'pre-wrap', maxHeight: 480, overflow: 'auto' }}>{JSON.stringify(r, null, 2)}</pre></Collapsible>
        </div>
      )}
    </div>
  )
}
