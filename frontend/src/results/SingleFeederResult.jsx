import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { FeederDiagram } from '../diagrams/Diagrams'
import { num } from '../lib/format'
import { KV, Notice, StatusBadge, Tabs } from '../components/ui'
import { ChecksTable, DataTable, Metric, SensitivityPanel, Warnings } from './common'

export const SF_SWEEP = (inp) => {
  const v = {}
  if (inp.installation === 'air') v.air_temp = 'Ambient air temperature (°C)'
  else {
    v.soil_temp = 'Soil temperature (°C)'
    v.depth = 'Burial depth (m)'
    v[inp.installation === 'buried' ? 'soil_resistivity' : 'duct_resistivity'] = inp.installation === 'buried' ? 'Soil thermal resistivity (K·m/W)' : 'Duct thermal resistivity (K·m/W)'
  }
  v.cable_length = 'Cable length (m)'
  if (inp.load_mode === 'current') v.current = 'Load current (A)'
  else v.power = `Load power (${inp.power_unit})`
  v.power_factor = 'Power factor'
  return v
}

function Chain({ chain, runs, iz }) {
  const items = [['Base', chain.base, 'A'], ['Ca ambient', chain.ambient], ['Cs soil/duct', chain.soil], ['Cd depth', chain.depth], ['Cg grouping', chain.group]]
  const total = chain.ambient * chain.soil * chain.depth * chain.group
  return (
    <div className="chain">
      {items.map(([l, v, u], i) => (
        <span key={l} style={{ display: 'contents' }}>
          {i > 0 && <span className="chain-op">×</span>}
          <span className="chain-item"><b>{u ? num(v, 0) : num(v, 3)}{u ? ' A' : ''}</b><span>{l}</span></span>
        </span>
      ))}
      <span className="chain-op">×</span>
      <span className="chain-item"><b>{runs}</b><span>run(s)</span></span>
      <span className="chain-op">=</span>
      <span className="chain-item chain-total"><b>{num(iz, 1)} A</b><span>Iz · total factor {num(total, 3)}</span></span>
    </div>
  )
}

const REJECT = { ampacity: 'Current rating below design current', voltage_drop: 'Voltage drop above limit', short_circuit: 'Short-circuit withstand insufficient' }

export default function SingleFeederResult({ inputs, result: r }) {
  const [tab, setTab] = useState('summary')
  const [spacing, setSpacing] = useState(r.spacings?.[0] || 'Touching')
  const [diagramOpt, setDiagramOpt] = useState('single')
  const s = r.single
  const rec = s?.recommended
  const bestPar = useMemo(() => (r.best_by_spacing?.length ? [...r.best_by_spacing].sort((a, b) => a.runs - b.runs || Number(a.size) - Number(b.size))[0] : null), [r])
  const shown = rec || bestPar
  const lim = inputs.voltage_drop_limit_pct
  const diag = diagramOpt === 'single' || !r.best_by_spacing.length ? (rec ? { runs: 1, spacing: 'Touching', size: rec.size } : null)
    : r.best_by_spacing.find((b) => b.spacing === diagramOpt)

  return (
    <div>
      <div className="result-hero">
        <Metric label="Design current Ib" value={num(r.design_current, 1)} unit="A" tip="Ib from the entered current, or from power: P/(V·pf·√3) for kW/MW, S/(V·√3) for kVA/MVA (√3 omitted for single phase)." />
        <Metric accent label={rec ? 'Recommended single run' : 'Smallest parallel option'} value={shown ? `${shown.runs > 1 ? `${shown.runs} × ` : ''}${shown.size}` : '—'} unit="mm²"
          sub={rec ? s.circuit : bestPar ? bestPar.circuit : 'No feasible configuration'} />
        <Metric label="Derated rating Iz" value={shown ? num(shown.derated_current, 1) : '—'} unit="A" sub={shown ? `${num(shown.current_per_run, 1)} A per run` : ''} />
        <Metric label="Utilisation Ib/Iz" value={shown ? num(shown.utilisation, 0) : '—'} unit="%" />
        <Metric label="Voltage drop" value={shown ? num(shown.voltage_drop, 2) : '—'} unit="%" sub={`limit ${lim} %`} />
        <Metric label="Short-circuit withstand" value={shown ? num(shown.short_circuit, 2) : '—'} unit="kA"
          sub={shown?.sc_status ? <StatusBadge status={shown.sc_status} label={`${shown.sc_status} vs ${num(shown.sc_required, 2)} kA`} /> : 'no fault level entered'} />
      </div>

      <Tabs value={tab} onChange={setTab} tabs={[
        { id: 'summary', label: 'Summary' },
        { id: 'options', label: 'All options', badge: (s?.solutions.length || 0) + (r.best_by_spacing?.length || 0) },
        { id: 'derating', label: 'Correction factors' },
        { id: 'diagram', label: 'Installation diagram' },
        { id: 'whatif', label: 'What-if' },
        { id: 'basis', label: 'Warnings & basis', badge: r.warnings.length || null, badgeTone: 'warn' },
      ]} />

      {tab === 'summary' && (
        <div className="section-gap">
          {r.status === 'no_solution' && <Notice tone="alert">No configuration in the rated range meets all criteria. Consider wider spacing, better backfill, a shorter route or a higher voltage level.</Notice>}
          {s?.all_fail_short_circuit && <Notice tone="alert">No single-run size passes the short-circuit check — the smallest thermally adequate size is shown. Review protection settings.</Notice>}
          <ChecksTable checks={r.checks} />
          {rec && (
            <div className="card">
              <h3 className="mt-0">Recommended single circuit</h3>
              <KV rows={[
                ['Circuit', s.circuit], ['Arrangement', r.installation_description],
                ['Governing constraint', s.governing, 'The check with the tightest margin for the selected size.'],
                ['Smaller sizes excluded', s.exclusions || '—'],
              ]} />
              <h4>Derating chain</h4>
              <Chain chain={rec.chain} runs={1} iz={rec.derated_current} />
            </div>
          )}
          {rec && bestPar && (
            <div className="card">
              <h3 className="mt-0">Single run vs parallel runs</h3>
              <p className="small muted">Both are technically feasible for these inputs. Neither is “cheapest” — that needs real prices (see <Link className="table-link" to="/comparison?tab=cost">cost estimate</Link>).</p>
              <div className="table-scroll">
                <table className="data-table">
                  <thead><tr><th>Option</th><th>Circuit</th><th className="num">Iz A</th><th className="num">Util %</th><th className="num">VD %</th><th className="num">Isc kA/cable</th><th>SC</th><th>Governing</th></tr></thead>
                  <tbody>
                    <tr className="row-rec"><td>Single run</td><td>{s.circuit}</td><td className="num">{num(rec.derated_current, 1)}</td><td className="num">{num(rec.utilisation, 0)}</td><td className="num">{num(rec.voltage_drop, 2)}</td><td className="num">{num(rec.short_circuit, 2)}</td><td><StatusBadge status={rec.sc_status || 'NOT_CHECKED'} /></td><td>{s.governing}</td></tr>
                    {r.best_by_spacing.map((b) => (
                      <tr key={b.spacing}><td>Parallel, {b.spacing === 'Touching' ? 'touching' : `${b.spacing} mm`}</td><td>{b.circuit}</td><td className="num">{num(b.derated_current, 1)}</td><td className="num">{num(b.utilisation, 0)}</td><td className="num">{num(b.voltage_drop, 2)}</td><td className="num">{num(b.short_circuit, 2)}</td><td><StatusBadge status={b.sc_status || 'NOT_CHECKED'} /></td><td>{b.governing}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {!rec && r.best_by_spacing.length > 0 && (
            <div className="card">
              <h3 className="mt-0">Parallel-run options (no single run is feasible)</h3>
              <DataTable rows={r.best_by_spacing} rowKey={(b) => b.spacing} columns={[
                { key: 'spacing', label: 'Spacing', render: (b) => (b.spacing === 'Touching' ? 'Touching' : `${b.spacing} mm`) },
                { key: 'circuit', label: 'Circuit' },
                { key: 'derated_current', label: 'Iz A', num: true, render: (b) => num(b.derated_current, 1) },
                { key: 'utilisation', label: 'Util %', num: true, render: (b) => num(b.utilisation, 0) },
                { key: 'voltage_drop', label: 'VD %', num: true, render: (b) => num(b.voltage_drop, 2) },
                { key: 'sc_status', label: 'SC', render: (b) => <StatusBadge status={b.sc_status || 'NOT_CHECKED'} /> },
                { key: 'governing', label: 'Governing constraint' },
              ]} />
            </div>
          )}
        </div>
      )}

      {tab === 'options' && (
        <div className="section-gap">
          <h3>Single-run sizes that pass</h3>
          <DataTable rows={s?.solutions || []} rowKey={(x) => x.size} rowClass={(x) => (x.recommended ? 'row-rec' : '')} empty="No single-run size passes all checks." columns={[
            { key: 'size', label: 'Size mm²', sortValue: (x) => Number(x.size), render: (x) => <>{x.size}{x.recommended && <span className="chip chip-brand" style={{ marginLeft: 8 }}>recommended</span>}</> },
            { key: 'derated_current', label: 'Iz A', num: true, render: (x) => num(x.derated_current, 1) },
            { key: 'utilisation', label: 'Ib/Iz %', num: true, render: (x) => num(x.utilisation, 0) },
            { key: 'voltage_drop', label: 'VD %', num: true, render: (x) => num(x.voltage_drop, 2) },
            { key: 'short_circuit', label: 'Isc kA', num: true, render: (x) => num(x.short_circuit, 2) },
            { key: 'sc_status', label: 'SC check', render: (x) => <StatusBadge status={x.sc_status || 'NOT_CHECKED'} /> },
          ]} />
          {Object.keys(r.rejections || {}).length > 0 && (
            <>
              <h3>Sizes rejected for a single run</h3>
              <div className="pill-row">{Object.entries(r.rejections).map(([size, why]) => <span key={size} className="chip">{size} mm² — {REJECT[why] || why}</span>)}</div>
            </>
          )}
          {r.matrix?.some((row) => Object.values(row.cells).some(Boolean)) && (
            <>
              <h3>Parallel-run matrix (minimum runs / utilisation)</h3>
              <p className="small muted">Every size against every group spacing: minimum number of parallel runs that satisfies all checks. Green = recommended for that spacing, red = fails the short-circuit check.</p>
              <div className="table-scroll">
                <table className="data-table matrix">
                  <thead><tr><th>Size mm²</th>{r.spacings.map((sp) => <th key={sp}>{sp === 'Touching' ? 'Touching' : `${sp} mm`}</th>)}</tr></thead>
                  <tbody>
                    {r.matrix.map((row) => (
                      <tr key={row.size}><td>{row.size}</td>
                        {r.spacings.map((sp) => {
                          const c = row.cells[sp]
                          return <td key={sp} className={!c ? '' : c.recommended ? 'm-rec' : c.sc_status === 'FAIL' ? 'm-fail' : 'm-ok'}>{c ? `${c.runs}R / ${num(c.utilisation, 0)}%${c.sc_status === 'FAIL' ? ' !' : ''}` : '—'}</td>
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3>Every feasible size × runs combination</h3>
              <Tabs small value={spacing} onChange={setSpacing} tabs={r.spacings.map((sp) => ({ id: sp, label: sp === 'Touching' ? 'Touching' : `${sp} mm`, badge: r.detailed_options?.[sp]?.length ?? 0 }))} />
              {r.detailed_options ? (
                <DataTable rows={r.detailed_options[spacing] || []} rowKey={(x) => `${x.size}-${x.runs}`} rowClass={(x) => (x.recommended ? 'row-rec' : x.sc_status === 'FAIL' ? 'row-fail' : '')} columns={[
                  { key: 'size', label: 'Size mm²', sortValue: (x) => Number(x.size) },
                  { key: 'runs', label: 'Runs', num: true },
                  { key: 'derated_current', label: 'Iz A', num: true, render: (x) => num(x.derated_current, 1) },
                  { key: 'current_per_run', label: 'A/run', num: true, render: (x) => num(x.current_per_run, 1) },
                  { key: 'utilisation', label: 'Util %', num: true, render: (x) => num(x.utilisation, 0) },
                  { key: 'voltage_drop', label: 'VD %', num: true, render: (x) => num(x.voltage_drop, 2) },
                  { key: 'short_circuit', label: 'Isc kA', num: true, render: (x) => num(x.short_circuit, 2) },
                  { key: 'sc_status', label: 'SC', render: (x) => <StatusBadge status={x.sc_status || 'NOT_CHECKED'} /> },
                ]} />
              ) : <p className="muted small">Not stored with the saved calculation — recalculate to list them.</p>}
            </>
          )}
        </div>
      )}

      {tab === 'derating' && (
        <div className="section-gap">
          {shown && (
            <div className="card">
              <h3 className="mt-0">Applied correction factors — {shown.runs > 1 ? `${shown.runs} × ` : ''}{shown.size} mm²</h3>
              <Chain chain={shown.chain} runs={shown.runs} iz={shown.derated_current} />
            </div>
          )}
          <div className="chart-card">
            <h3 className="chart-title">Total correction factor by size (before grouping)</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={Object.entries(r.derating_by_size).map(([size, f]) => ({ size, total: f.total }))}>
                <CartesianGrid stroke="#eee" vertical={false} />
                <XAxis dataKey="size" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 'auto']} tick={{ fontSize: 11 }} />
                <ReferenceLine y={1} stroke="#999" strokeDasharray="4 3" />
                <Tooltip formatter={(v) => num(v, 3)} />
                <Bar dataKey="total" fill="var(--brand-red)" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <DataTable rows={Object.entries(r.derating_by_size).map(([size, f]) => ({ size, ...f }))} rowKey={(x) => x.size} columns={[
            { key: 'size', label: 'Size mm²', sortValue: (x) => Number(x.size) },
            { key: 'ambient', label: 'Ca', num: true, tip: 'Ambient / ground temperature factor √((θmax−θamb)/(θmax−θref)), incl. ×0.90 for PVC.', render: (x) => num(x.ambient, 3) },
            { key: 'soil', label: 'Cs', num: true, tip: 'Soil or duct thermal resistivity factor (nearest tabled value).', render: (x) => num(x.soil, 3) },
            { key: 'depth', label: 'Cd', num: true, tip: 'Laying depth factor (nearest tabled value).', render: (x) => num(x.depth, 3) },
            { key: 'total', label: 'Ca·Cs·Cd', num: true, render: (x) => num(x.total, 3) },
          ]} />
          <p className="small muted">Grouping factor Cg applies to parallel runs and depends on the number of groups and their spacing; it is shown in each option's chain.</p>
        </div>
      )}

      {tab === 'diagram' && (
        <div className="section-gap">
          {r.best_by_spacing.length > 0 && (
            <div className="toolbar">
              <span className="small muted">Show:</span>
              {rec && <button className={`btn-sm ${diagramOpt === 'single' ? 'btn-sm-primary' : ''}`} onClick={() => setDiagramOpt('single')}>Single run</button>}
              {r.best_by_spacing.map((b) => <button key={b.spacing} className={`btn-sm ${diagramOpt === b.spacing ? 'btn-sm-primary' : ''}`} onClick={() => setDiagramOpt(b.spacing)}>{b.runs} runs, {b.spacing === 'Touching' ? 'touching' : `${b.spacing} mm`}</button>)}
            </div>
          )}
          {diag ? (
            <FeederDiagram installation={inputs.installation} arrangement={r.arrangement} coreType={inputs.core_type} runs={diag.runs} spacing={diag.spacing}
              depth={inputs.depth} material={inputs.material} label={`${diag.runs > 1 ? `${diag.runs} × ` : ''}${diag.size} mm² · ${r.installation_description}`} />
          ) : <Notice>No feasible configuration to draw.</Notice>}
          <p className="small muted">The full report (PDF → Detailed) contains the original engine's installation drawings.</p>
        </div>
      )}

      {tab === 'whatif' && <SensitivityPanel mode="single_feeder" inputs={inputs} variables={SF_SWEEP(inputs)} />}

      {tab === 'basis' && (
        <div className="section-gap">
          <Warnings warnings={r.warnings} />
          <div className="card">
            <h3 className="mt-0">Calculation basis</h3>
            <ul className="small">{r.basis.map((b) => <li key={b}>{b}</li>)}</ul>
            <KV rows={[
              ['Rating table', r.table_key], ['Arrangement', `${r.arrangement_label} (${r.arrangement})`],
              ['Max conductor temperature used', `${r.constants.max_temp_used} °C`],
              ['Reference temperature — ground / air', `${r.constants.REF_TEMP_GROUND} / ${r.constants.REF_TEMP_AIR} °C`],
              ['Adiabatic k (Cu / Al, XLPE)', `${r.constants.K_ADIABATIC.a} / ${r.constants.K_ADIABATIC.b}`],
            ]} />
          </div>
        </div>
      )}
    </div>
  )
}
