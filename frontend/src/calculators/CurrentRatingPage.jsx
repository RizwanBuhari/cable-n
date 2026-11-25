import { useState } from 'react'
import { useShareableCalc } from '../components/ChatPanel'
import { Icon } from '../components/icons'
import { OutputBar, TemplatePicker } from '../components/Outputs'
import { Choice, ErrorBox, Field, KV, Notice, NumInput, PageHeader, Panel, Spinner, StatTile, StatusBadge, Tabs, Toggle, VerificationNotice } from '../components/ui'
import { BankDiagram } from '../diagrams/Diagrams'
import { num } from '../lib/format'
import { getPrefs } from '../lib/store'
import { useCalculator } from '../lib/useCalculator'
import { DataTable, RunInfo, SensitivityPanel, Warnings } from '../results/common'

const bank = () => ({ rows: 2, cols: 3, h_pitch: 250, v_pitch: 250, top_depth: 1.0, circuits: null, positions: [] })
function defaults() {
  const e = getPrefs().engineering
  return {
    installation: 'duct', soil_rho: e.soil_resistivity, soil_temp: e.soil_temp, has_backfill: false, backfill_rho: 1.0, rho_choice: 'worst',
    armored: true, material: 'cu', gaps: [], interbank_override: null,
    banks: [{ ...bank(), positions: [{ row: 1, col: 1, desig: '3x240', load: 300 }, { row: 1, col: 2, desig: '3x240', load: 220 }, { row: 2, col: 2, desig: '1x400', load: null }] }],
  }
}
function payloadOf(i) {
  const p = { installation: i.installation, soil_rho: i.soil_rho, soil_temp: i.soil_temp, armored: i.armored, material: i.material,
    banks: i.banks.map((b) => ({ rows: b.rows, cols: b.cols, h_pitch: b.h_pitch, top_depth: b.top_depth, ...(b.rows > 1 ? { v_pitch: b.v_pitch } : {}),
      ...(b.circuits !== null && b.circuits !== undefined && b.circuits !== '' ? { circuits: b.circuits } : {}),
      positions: b.positions.filter((q) => q.row <= b.rows && q.col <= b.cols).map((q) => ({ row: q.row, col: q.col, desig: q.desig, load: q.load ?? null })) })),
    gaps: i.banks.length > 1 ? i.banks.slice(1).map((_, n) => i.gaps[n] ?? 1) : [] }
  if (i.has_backfill) Object.assign(p, { backfill_rho: i.backfill_rho, rho_choice: i.rho_choice })
  if (i.banks.length > 1 && i.interbank_override !== null && i.interbank_override !== undefined) p.interbank_override = i.interbank_override
  return p
}

function fromPayload(p) {
  return { ...defaults(), ...p, has_backfill: p.backfill_rho !== undefined && p.backfill_rho !== null, backfill_rho: p.backfill_rho ?? 1.0, rho_choice: p.rho_choice || 'worst',
    interbank_override: p.interbank_override ?? null, gaps: p.gaps || [], banks: p.banks.map((b) => ({ v_pitch: 250, circuits: null, ...b })) }
}

export default function CurrentRatingPage() {
  const c = useCalculator('current_rating', defaults, payloadOf, fromPayload)
  const { inputs: i, set } = c
  const [cell, setCell] = useState({ bank: 1, row: 1, col: 1 })
  const [tab, setTab] = useState('results')
  const [picked, setPicked] = useState(null)
  useShareableCalc(c.run && !c.outdated ? { mode: 'current_rating', inputs: c.payload, label: 'current-rating check' } : null)
  const setBank = (n, p) => set((x) => ({ banks: x.banks.map((b, k) => (k === n ? { ...b, ...p } : b)) }))
  const b = i.banks[cell.bank - 1] || i.banks[0]
  const pos = b?.positions.find((q) => q.row === cell.row && q.col === cell.col)
  const setPos = (p) => setBank(cell.bank - 1, {
    positions: p === null ? b.positions.filter((q) => !(q.row === cell.row && q.col === cell.col))
      : [...b.positions.filter((q) => !(q.row === cell.row && q.col === cell.col)), { row: cell.row, col: cell.col, desig: '3x240', load: null, ...pos, ...p }],
  })
  const r = c.run?.result
  const occupied = i.banks.reduce((s, x) => s + x.positions.length, 0)

  async function calculate() {
    const res = await c.execute()
    if (res) setTimeout(() => document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }
  const diagramPositions = r && !c.outdated ? r.positions : i.banks.flatMap((x, n) => x.positions.map((q) => ({ ...q, bank: n + 1 })))

  return (
    <div>
      <PageHeader icon={Icon.grid} title="Current-rating verification" hint="Mode 3 — rate an existing or proposed duct bank or buried group (table method with grouping, depth, soil and inter-bank factors)."
        actions={<><TemplatePicker mode="current_rating" onApply={c.loadPayload} /><button className="btn-sm" onClick={c.reset}>{Icon.refresh} New</button></>} />
      <Notice tone="info">This checks <b>current rating only</b>. It does not verify voltage drop, short-circuit withstand or any other requirement.</Notice>

      <div className="split mt-16">
        <Panel title="Site" icon={Icon.mapPin}>
          <Choice value={i.installation} onChange={(v) => set({ installation: v })} options={[{ value: 'duct', label: 'Duct bank(s)' }, { value: 'buried', label: 'Direct buried group(s)' }]} />
          <div className="form-grid mt-16">
            <Field label="Native soil resistivity" unit="K·m/W"><NumInput value={i.soil_rho} onChange={(v) => set({ soil_rho: v })} /></Field>
            <Field label="Soil temperature" unit="°C"><NumInput value={i.soil_temp} onChange={(v) => set({ soil_temp: v })} /></Field>
            <Field label="Conductor"><select value={i.material} onChange={(e) => set({ material: e.target.value })}><option value="cu">Copper</option><option value="al">Aluminium</option></select></Field>
            <Field label="Armour"><select value={String(i.armored)} onChange={(e) => set({ armored: e.target.value === 'true' })}><option value="true">Armoured</option><option value="false">Unarmoured</option></select></Field>
          </div>
          <div className="mt-16"><Toggle checked={i.has_backfill} onChange={(v) => set({ has_backfill: v })} label="Special backfill / concrete envelope" /></div>
          {i.has_backfill && (
            <div className="form-grid mt-8">
              <Field label="Envelope resistivity" unit="K·m/W" hint="bentonite ≈ 0.9, concrete ≈ 1.0"><NumInput value={i.backfill_rho} onChange={(v) => set({ backfill_rho: v })} /></Field>
              <Field label="Resistivity used for factors">
                <select value={i.rho_choice} onChange={(e) => set({ rho_choice: e.target.value })}>
                  <option value="worst">Worst of both (conservative)</option><option value="native">Native soil</option><option value="envelope">Envelope</option>
                </select>
              </Field>
            </div>
          )}
          {i.banks.length > 1 && (
            <div className="form-grid mt-16">
              {i.banks.slice(1).map((_, n) => (
                <Field key={n} label={`Clear gap bank ${n + 1} → ${n + 2}`} unit="m"><NumInput value={i.gaps[n] ?? 1} onChange={(v) => set((x) => { const g = [...x.gaps]; g[n] = v; return { gaps: g } })} /></Field>
              ))}
              <Field label="Inter-bank factor override" hint="Blank = conservative n-bank group factor; 1.0 = independent banks"><NumInput value={i.interbank_override} min={0} max={1} step={0.01} onChange={(v) => set({ interbank_override: v })} /></Field>
            </div>
          )}
        </Panel>

        <Panel title="Banks and positions" icon={Icon.grid} count={occupied} actions={(
          <div className="panel-actions">
            {i.banks.length < 3 && <button className="btn-sm" onClick={() => set((x) => ({ banks: [...x.banks, bank()], gaps: [...x.gaps, 1] }))}>{Icon.plus} Add bank</button>}
          </div>
        )}>
          <Tabs small value={String(cell.bank)} onChange={(v) => setCell({ bank: Number(v), row: 1, col: 1 })} tabs={i.banks.map((_, n) => ({ id: String(n + 1), label: `Bank ${n + 1}`, badge: i.banks[n].positions.length }))} />
          {b && (
            <>
              <div className="form-grid">
                <Field label="Rows"><NumInput value={b.rows} min={1} max={6} step={1} onChange={(v) => setBank(cell.bank - 1, { rows: v })} /></Field>
                <Field label="Columns"><NumInput value={b.cols} min={1} max={12} step={1} onChange={(v) => setBank(cell.bank - 1, { cols: v })} /></Field>
                <Field label="Horizontal pitch" unit="mm"><NumInput value={b.h_pitch} onChange={(v) => setBank(cell.bank - 1, { h_pitch: v })} /></Field>
                {b.rows > 1 && <Field label="Vertical pitch" unit="mm"><NumInput value={b.v_pitch} onChange={(v) => setBank(cell.bank - 1, { v_pitch: v })} /></Field>}
                <Field label="Depth to top-row centre" unit="m"><NumInput value={b.top_depth} onChange={(v) => setBank(cell.bank - 1, { top_depth: v })} /></Field>
                <Field label="Circuits for grouping" hint={`Blank = occupied positions (${b.positions.length})`}><NumInput value={b.circuits} min={0} max={24} step={1} onChange={(v) => setBank(cell.bank - 1, { circuits: v })} /></Field>
              </div>
              <p className="small muted mt-8">Click a position, then set its cable: <b>1x&lt;size&gt;</b> = three single-core cables in trefoil in the duct, <b>3x&lt;size&gt;</b> = one three-core cable.</p>
              <div className="bank-grid" style={{ gridTemplateColumns: `repeat(${Math.min(b.cols || 1, 12)}, minmax(54px, 1fr))` }}>
                {Array.from({ length: (b.rows || 1) * (b.cols || 1) }, (_, k) => {
                  const rr = Math.floor(k / b.cols) + 1
                  const cc = (k % b.cols) + 1
                  const q = b.positions.find((x) => x.row === rr && x.col === cc)
                  const isSel = cell.row === rr && cell.col === cc
                  return (
                    <button key={k} className={`bank-cell ${q ? 'filled' : ''} ${isSel ? 'sel' : ''}`} onClick={() => setCell({ ...cell, row: rr, col: cc })}>
                      <span>{q ? q.desig : 'empty'}</span>
                      {q?.load ? <span className="muted">{q.load} A</span> : <span className="muted">R{rr}·C{cc}</span>}
                    </button>
                  )
                })}
              </div>
              <div className="card mt-16" style={{ padding: 16 }}>
                <strong className="small">Position B{cell.bank} R{cell.row}-C{cell.col}</strong>
                <div className="form-grid mt-8">
                  <Field label="Cable" hint="e.g. 1x500 or 3x150">
                    <input list="desigs" value={pos?.desig || ''} placeholder="empty" onChange={(e) => (e.target.value.trim() ? setPos({ desig: e.target.value.trim().toLowerCase() }) : setPos(null))} />
                  </Field>
                  <Field label="Operating load" unit="A" hint="Optional — gives utilisation"><NumInput value={pos?.load ?? null} disabled={!pos} onChange={(v) => setPos({ load: v })} /></Field>
                </div>
                <datalist id="desigs">{['1x95', '1x120', '1x150', '1x185', '1x240', '1x300', '1x400', '1x500', '1x630', '3x50', '3x70', '3x95', '3x120', '3x150', '3x185', '3x240', '3x300'].map((d) => <option key={d} value={d} />)}</datalist>
                <div className="row-actions mt-8">
                  {pos && <button className="btn-sm btn-sm-danger" onClick={() => setPos(null)}>Clear position</button>}
                  {i.banks.length > 1 && <button className="btn-sm btn-sm-danger" onClick={() => { set((x) => ({ banks: x.banks.filter((_, n) => n !== cell.bank - 1), gaps: x.gaps.filter((_, n) => n !== Math.max(0, cell.bank - 2)) })); setCell({ bank: 1, row: 1, col: 1 }) }}>Remove bank {cell.bank}</button>}
                </div>
              </div>
            </>
          )}
        </Panel>
      </div>

      <div className="mt-16">
        <BankDiagram banks={i.banks.map((x) => ({ ...x, v_pitch: x.rows > 1 ? x.v_pitch : 0 }))} gaps={i.banks.slice(1).map((_, n) => i.gaps[n] ?? 1)} positions={diagramPositions}
          installation={i.installation} selected={cell} onSelect={(s) => { setCell(s); setPicked(s) }} />
      </div>
      <div className="toolbar mt-16">
        <span className="small muted">{occupied} occupied position(s) in {i.banks.length} bank(s).</span>
        <span className="spacer" />
        <button className="btn-primary" onClick={calculate} disabled={c.busy || !occupied}>{c.busy ? <Spinner light /> : Icon.play} Calculate ratings</button>
      </div>

      <ErrorBox error={c.error} />
      {r && (
        <div id="results" className="mt-16">
          <h2 className="section-title">Ratings</h2>
          <RunInfo run={c.run} outdated={c.outdated} onRecalc={calculate} busy={c.busy} />
          <div className="stat-grid">
            <StatTile label="Positions rated" value={r.summary.positions} tone="neutral" />
            <StatTile label="With load entered" value={r.summary.loaded} tone="info" />
            <StatTile label="Overloaded" value={r.summary.overload} tone={r.summary.overload ? 'alert' : 'good'} />
            <StatTile label="Lowest rating" value={`${num(r.summary.min_rating, 0)} A`} tone="brand" />
          </div>
          <Tabs value={tab} onChange={setTab} tabs={[{ id: 'results', label: 'Position ratings' }, { id: 'banks', label: 'Banks & factors' }, { id: 'whatif', label: 'What-if' }, { id: 'limits', label: 'Limitations', badge: r.warnings.length, badgeTone: 'warn' }]} />
          {tab === 'results' && (
            <DataTable rows={r.positions} rowKey={(p) => p.pos} rowClass={(p) => (p.status === 'OVERLOAD' ? 'row-fail' : '')} onRow={(p) => setPicked({ bank: p.bank, row: p.row, col: p.col })} columns={[
              { key: 'pos', label: 'Position' }, { key: 'config_label', label: 'Cable' },
              { key: 'depth', label: 'Depth m', num: true, render: (p) => num(p.depth, 2) },
              { key: 'base', label: 'Base A', num: true, tip: 'Tabulated rating for the arrangement before corrections.' },
              { key: 'ambient', label: 'Ca', num: true, render: (p) => num(p.ambient, 3) }, { key: 'soil', label: 'Cs', num: true, render: (p) => num(p.soil, 2) },
              { key: 'depth_f', label: 'Cd', num: true, render: (p) => num(p.depth_f, 2) }, { key: 'cg', label: 'Cg', num: true, render: (p) => num(p.cg, 2) },
              { key: 'inter', label: 'Cint', num: true, tip: 'Inter-bank factor', render: (p) => num(p.inter, 2) },
              { key: 'iz', label: 'Rating A', num: true, render: (p) => <b>{num(p.iz, 1)}</b> },
              { key: 'load', label: 'Load A', num: true, render: (p) => (p.load === null ? '—' : num(p.load, 0)) },
              { key: 'util', label: 'Util %', num: true, render: (p) => (p.util === null || p.util === undefined ? '—' : num(p.util, 0)) },
              { key: 'status', label: 'Status', render: (p) => (p.status ? <StatusBadge status={p.status} /> : <span className="muted small">no load</span>) },
            ]} />
          )}
          {tab === 'banks' && (
            <div className="section-gap">
              <KV rows={[['Effective resistivity used', `${r.rho_used} K·m/W`], ['Native / envelope', `${r.soil_rho} / ${r.backfill_rho ?? '—'} K·m/W`], ['Inter-bank factor', `${num(r.inter, 2)} — ${r.inter_note}`]]} />
              <DataTable rows={r.banks} rowKey={(x) => x.id} columns={[
                { key: 'id', label: 'Bank' }, { key: 'grid', label: 'Grid', render: (x) => `${x.rows} × ${x.cols}` },
                { key: 'h_pitch', label: 'Pitch mm', num: true }, { key: 'circuits', label: 'Circuits', num: true },
                { key: 'spacing_key', label: 'Table spacing' }, { key: 'cg', label: 'Cg', num: true, render: (x) => num(x.cg, 2) }, { key: 'cg_note', label: 'Note' }]} />
            </div>
          )}
          {tab === 'whatif' && <SensitivityPanel mode="current_rating" inputs={c.payload} variables={{ soil_rho: 'Soil thermal resistivity (K·m/W)', soil_temp: 'Soil temperature (°C)' }} />}
          {tab === 'limits' && (
            <div className="section-gap">
              <Warnings warnings={r.warnings} title="Warnings" />
              <div className="card"><h3 className="mt-0">Method limitations (from the engine)</h3><ul className="small">{r.limitations.map((l) => <li key={l}>{l}</li>)}</ul></div>
            </div>
          )}
          {picked && (() => {
            const p = r.positions.find((x) => x.bank === picked.bank && x.row === picked.row && x.col === picked.col)
            return p ? <Notice tone="info">{p.pos}: {p.config_label} — rating {num(p.iz, 1)} A = {p.base} A × Ca {num(p.ambient, 3)} × Cs {num(p.soil, 2)} × Cd {num(p.depth_f, 2)} × Cg {num(p.cg, 2)} × Cint {num(p.inter, 2)}{p.note ? ` (${p.note})` : ''}</Notice> : null
          })()}
          <div className="mt-16"><VerificationNotice /></div>
          <div className="sticky-actions"><OutputBar mode="current_rating" inputs={c.payload} run={c.run} outdated={c.outdated} saved={c.saved} onSaved={c.setSaved} /></div>
        </div>
      )}
    </div>
  )
}
