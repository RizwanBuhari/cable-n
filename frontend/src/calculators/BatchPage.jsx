import { useEffect, useMemo, useRef, useState } from 'react'
import { useShareableCalc } from '../components/ChatPanel'
import { Icon } from '../components/icons'
import { OutputBar, TemplatePicker } from '../components/Outputs'
import { Choice, ErrorBox, Field, NumInput, PageHeader, Panel, ProgressBar, Spinner, Toggle, VerificationNotice } from '../components/ui'
import { api, ApiError, pollJob, saveBlob } from '../lib/api'
import { stableKey } from '../lib/format'
import { getPrefs } from '../lib/store'
import { useCalculator } from '../lib/useCalculator'
import BatchResult from '../results/BatchResult'
import { RunInfo } from '../results/common'

const newFeeder = (n) => ({ _k: Math.random().toString(36).slice(2), tag: `F-${String(n).padStart(2, '0')}`, name: '', load_mode: 'current', current: 100, power: null, power_unit: 'KW', cable_length: 100, power_factor: null, voltage_drop_limit_pct: null })

function defaults() {
  const e = getPrefs().engineering
  return {
    common: { voltage: 415, phase: 'three', voltage_drop_limit_pct: e.voltage_drop_limit_pct, power_factor: e.power_factor, core_type: '3C', armored: true, material: 'cu',
      installation: 'buried', soil_resistivity: e.soil_resistivity, duct_resistivity: e.duct_resistivity, soil_temp: e.soil_temp, depth: e.depth, air_temp: e.air_temp,
      sc_check: false, fault_kA: 25, fault_time: e.fault_time },
    feeders: [1, 2, 3].map(newFeeder).map((f, i) => ({ ...f, current: [80, 160, 320][i], cable_length: [120, 200, 90][i] })),
    arrangement: null,
  }
}

function payloadOf(i) {
  const c = i.common
  const common = { voltage: c.voltage, phase: c.phase, voltage_drop_limit_pct: c.voltage_drop_limit_pct, power_factor: c.power_factor, core_type: c.core_type,
    armored: c.armored, material: c.material, installation: c.installation, sc_check: c.sc_check }
  if (c.installation === 'buried') Object.assign(common, { soil_resistivity: c.soil_resistivity, soil_temp: c.soil_temp, depth: c.depth })
  if (c.installation === 'duct') Object.assign(common, { duct_resistivity: c.duct_resistivity, soil_temp: c.soil_temp, depth: c.depth })
  if (c.installation === 'air') common.air_temp = c.air_temp
  if (c.sc_check) Object.assign(common, { fault_kA: c.fault_kA, fault_time: c.fault_time })
  const feeders = i.feeders.map(({ _k, ...f }) => {
    const o = { tag: f.tag, name: f.name, load_mode: f.load_mode, cable_length: f.cable_length, power_factor: f.power_factor, voltage_drop_limit_pct: f.voltage_drop_limit_pct }
    if (f.load_mode === 'current') o.current = f.current
    else Object.assign(o, { power: f.power, power_unit: f.power_unit })
    return o
  })
  return { common, feeders, arrangement: i.arrangement || null }
}

function rowErrors(f, common) {
  const e = []
  if (!f.tag?.trim()) e.push('tag')
  if (f.load_mode === 'current' ? !(f.current > 0) : !(f.power > 0)) e.push('load')
  if (f.load_mode === 'power' && ['KW', 'MW'].includes(f.power_unit) && !((f.power_factor ?? common.power_factor) > 0)) e.push('pf')
  if (!(f.cable_length >= 0.1)) e.push('length')
  return e
}

export default function BatchPage() {
  const c = useCalculator('batch', defaults, payloadOf)
  const { inputs: i } = c
  const [sel, setSel] = useState(new Set())
  const [q, setQ] = useState('')
  const [bulk, setBulk] = useState({ field: 'cable_length', value: '' })
  const [job, setJob] = useState(null)
  const [importMsg, setImportMsg] = useState(null)
  const ctl = useRef(null)
  const fileRef = useRef(null)
  const cm = i.common
  useEffect(() => {
    if (i.feeders.some((f) => !f._k)) c.set((x) => ({ feeders: x.feeders.map((f) => (f._k ? f : { ...f, _k: Math.random().toString(36).slice(2) })) }))
  }, [i.feeders]) // eslint-disable-line react-hooks/exhaustive-deps
  const setCommon = (p) => c.set((x) => ({ common: { ...x.common, ...p } }))
  const setFeeders = (fn) => c.set((x) => ({ feeders: fn(x.feeders) }))
  const upd = (k, p) => setFeeders((fs) => fs.map((f) => (f._k === k ? { ...f, ...p } : f)))
  const dupTags = useMemo(() => { const seen = {}; i.feeders.forEach((f) => { seen[f.tag] = (seen[f.tag] || 0) + 1 }); return seen }, [i.feeders])
  const visible = i.feeders.filter((f) => !q || `${f.tag} ${f.name}`.toLowerCase().includes(q.toLowerCase()))
  const badRows = i.feeders.filter((f) => rowErrors(f, cm).length || dupTags[f.tag] > 1).length
  useShareableCalc(c.run && !c.outdated ? { mode: 'batch', inputs: c.payload, label: 'batch schedule' } : null)

  async function runJob() {
    c.setError(null)
    const payload = c.payload
    ctl.current = new AbortController()
    setJob({ status: 'queued', done: 0, total: payload.feeders.length })
    try {
      const { job_id } = await api('/calculations/batch/jobs', { method: 'POST', body: { inputs: payload } })
      const j = await pollJob(job_id, setJob, { signal: ctl.current.signal })
      const out = j.result
      c.setRun({ result: out.result, summary: out.summary, inputsKey: stableKey(payload), engine_version: out.engine_version, at: new Date().toISOString() })
      setTimeout(() => document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' }), 50)
    } catch (e) {
      if (e.name !== 'AbortError') c.setError(e)
    } finally {
      setJob(null)
    }
  }

  async function importFile(file) {
    setImportMsg(null)
    const fd = new FormData()
    fd.append('file', file)
    try {
      const r = await api('/calculations/batch/import', { method: 'POST', form: fd })
      setFeeders(() => r.feeders.map((f, n) => ({ ...newFeeder(n + 1), ...f })))
      setImportMsg({ ok: true, text: `Imported ${r.feeders.length} feeders.`, problems: r.problems })
    } catch (e) {
      setImportMsg({ ok: false, text: e.message })
    }
  }
  async function template() {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/calculations/batch/template.xlsx`)
      if (!res.ok) throw new ApiError(res.status, 'Template download failed')
      saveBlob(await res.blob(), 'cable-n-feeder-template.xlsx')
    } catch (e) { setImportMsg({ ok: false, text: e.message }) }
  }
  function applyBulk() {
    const v = bulk.value === '' ? null : ['load_mode', 'power_unit'].includes(bulk.field) ? bulk.value : Number(bulk.value)
    setFeeders((fs) => fs.map((f) => (sel.has(f._k) ? { ...f, [bulk.field]: v } : f)))
  }

  const fc = (k) => ({ value: cm[k], onChange: (v) => setCommon({ [k]: v }) })
  return (
    <div>
      <PageHeader icon={Icon.layers} title="Batch cable schedule" hint="Mode 2 — common construction and installation, many feeders. Each feeder is sized independently (single run preferred, parallel runs as fallback)."
        actions={<><TemplatePicker mode="batch" onApply={c.loadPayload} /><button className="btn-sm" onClick={c.reset}>{Icon.refresh} New</button></>} />
      {c.saved && <div className="notice notice-info mb-16">{Icon.save}<div>Editing saved schedule “{c.saved.title}”.</div></div>}

      <Panel title="Common parameters" icon={Icon.settings}>
        <div className="form-grid">
          <Field label="Phases"><select value={cm.phase} onChange={(e) => setCommon({ phase: e.target.value })}><option value="three">Three-phase</option><option value="single">Single-phase</option></select></Field>
          <Field label="Voltage" unit="V"><NumInput {...fc('voltage')} min={1} /></Field>
          <Field label="Default VD limit" unit="%"><NumInput {...fc('voltage_drop_limit_pct')} min={0} max={100} /></Field>
          <Field label="Default power factor"><NumInput {...fc('power_factor')} min={0} max={1} step={0.01} /></Field>
          <Field label="Conductor"><select value={cm.material} onChange={(e) => setCommon({ material: e.target.value })}><option value="cu">Copper</option><option value="al">Aluminium</option></select></Field>
          <Field label="Cores"><select value={cm.core_type} onChange={(e) => setCommon({ core_type: e.target.value })}><option value="1C">Single-core</option><option value="3C">Three-core</option></select></Field>
          <Field label="Armour"><select value={String(cm.armored)} onChange={(e) => setCommon({ armored: e.target.value === 'true' })}><option value="true">Armoured</option><option value="false">Unarmoured</option></select></Field>
        </div>
        <div className="form-section">
          <h3>Installation</h3>
          <p>As in the original batch mode, ratings use 90 °C XLPE tables and equal fault sharing between parallel runs.</p>
          <Choice value={cm.installation} onChange={(v) => setCommon({ installation: v })} options={[{ value: 'buried', label: 'Direct buried' }, { value: 'duct', label: 'In duct' }, { value: 'air', label: 'In air' }]} />
          <div className="form-grid mt-16">
            {cm.installation === 'air' ? <Field label="Air temperature" unit="°C"><NumInput {...fc('air_temp')} /></Field> : (
              <>
                <Field label="Soil temperature" unit="°C"><NumInput {...fc('soil_temp')} /></Field>
                {cm.installation === 'buried'
                  ? <Field label="Soil resistivity" unit="K·m/W"><NumInput {...fc('soil_resistivity')} /></Field>
                  : <Field label="Duct resistivity" unit="K·m/W"><NumInput {...fc('duct_resistivity')} /></Field>}
                <Field label="Depth" unit="m"><NumInput {...fc('depth')} /></Field>
              </>
            )}
          </div>
          <div className="mt-16"><Toggle checked={cm.sc_check} onChange={(v) => setCommon({ sc_check: v })} label="Check short-circuit adequacy" /></div>
          {cm.sc_check && (
            <div className="form-grid mt-8">
              <Field label="Fault current" unit="kA"><NumInput {...fc('fault_kA')} /></Field>
              <Field label="Clearing time" unit="s"><NumInput {...fc('fault_time')} /></Field>
            </div>
          )}
        </div>
      </Panel>

      <Panel title="Feeders" icon={Icon.layers} count={i.feeders.length} className="mt-16" actions={(
        <div className="panel-actions">
          <button className="btn-sm" onClick={template}>{Icon.download} Excel template</button>
          <button className="btn-sm" onClick={() => fileRef.current?.click()}>{Icon.upload} Import Excel</button>
          <input ref={fileRef} type="file" accept=".xlsx,.xlsm" hidden onChange={(e) => { if (e.target.files[0]) importFile(e.target.files[0]); e.target.value = '' }} />
        </div>
      )}>
        {importMsg && (
          <div className={importMsg.ok ? 'notice notice-good mb-16' : 'error mb-16'}>
            <div>{importMsg.text}{importMsg.problems?.length > 0 && <ul>{importMsg.problems.map((p, n) => <li key={n}>{p}</li>)}</ul>}</div>
          </div>
        )}
        <div className="filter-bar">
          <div className="search-field"><input placeholder="Search tag or name" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <button className="btn-sm btn-sm-primary" onClick={() => setFeeders((fs) => [...fs, newFeeder(fs.length + 1)])}>{Icon.plus} Add feeder</button>
          {sel.size > 0 && (
            <>
              <button className="btn-sm" onClick={() => setFeeders((fs) => [...fs, ...fs.filter((f) => sel.has(f._k)).map((f) => ({ ...f, _k: Math.random().toString(36).slice(2), tag: `${f.tag}-copy` }))])}>{Icon.copy} Duplicate ({sel.size})</button>
              <button className="btn-sm btn-sm-danger" onClick={() => { setFeeders((fs) => fs.filter((f) => !sel.has(f._k))); setSel(new Set()) }}>{Icon.trash} Remove ({sel.size})</button>
              <select value={bulk.field} onChange={(e) => setBulk({ ...bulk, field: e.target.value })} aria-label="Bulk field">
                <option value="cable_length">Length (m)</option><option value="current">Current (A)</option><option value="power_factor">Power factor</option><option value="voltage_drop_limit_pct">VD limit %</option>
              </select>
              <input style={{ width: 110 }} value={bulk.value} onChange={(e) => setBulk({ ...bulk, value: e.target.value })} placeholder="value / blank" />
              <button className="btn-sm" onClick={applyBulk}>Apply to selected</button>
            </>
          )}
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th><input type="checkbox" aria-label="Select all" checked={sel.size > 0 && sel.size === i.feeders.length} onChange={(e) => setSel(e.target.checked ? new Set(i.feeders.map((f) => f._k)) : new Set())} /></th>
                <th>Tag</th><th>Name</th><th>Load as</th><th>Load</th><th>Unit</th><th>Length m</th><th>PF override</th><th>VD % override</th><th></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((f) => {
                const er = rowErrors(f, cm)
                const dup = dupTags[f.tag] > 1
                return (
                  <tr key={f._k} className={er.length || dup ? 'row-fail' : ''}>
                    <td><input type="checkbox" checked={sel.has(f._k)} onChange={(e) => { const s = new Set(sel); if (e.target.checked) s.add(f._k); else s.delete(f._k); setSel(s) }} aria-label={`Select ${f.tag}`} /></td>
                    <td><input className="cell-input" value={f.tag} onChange={(e) => upd(f._k, { tag: e.target.value })} title={dup ? 'Duplicate tag' : ''} /></td>
                    <td><input className="cell-input" value={f.name || ''} onChange={(e) => upd(f._k, { name: e.target.value })} /></td>
                    <td><select className="cell-input" value={f.load_mode} onChange={(e) => upd(f._k, { load_mode: e.target.value })}><option value="current">Current</option><option value="power">Power</option></select></td>
                    <td><NumInput className="cell-input" value={f.load_mode === 'current' ? f.current : f.power} onChange={(v) => upd(f._k, f.load_mode === 'current' ? { current: v } : { power: v })} /></td>
                    <td>{f.load_mode === 'current' ? 'A' : <select className="cell-input" value={f.power_unit || 'KW'} onChange={(e) => upd(f._k, { power_unit: e.target.value })}><option value="KW">kW</option><option value="KVA">kVA</option><option value="MW">MW</option><option value="MVA">MVA</option></select>}</td>
                    <td><NumInput className="cell-input" value={f.cable_length} onChange={(v) => upd(f._k, { cable_length: v })} /></td>
                    <td><NumInput className="cell-input" value={f.power_factor} placeholder={String(cm.power_factor)} onChange={(v) => upd(f._k, { power_factor: v })} /></td>
                    <td><NumInput className="cell-input" value={f.voltage_drop_limit_pct} placeholder={String(cm.voltage_drop_limit_pct)} onChange={(v) => upd(f._k, { voltage_drop_limit_pct: v })} /></td>
                    <td><button className="table-row-delete" onClick={() => setFeeders((fs) => fs.filter((x) => x._k !== f._k))} aria-label="Remove">{Icon.trash}</button></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {badRows > 0 && <p className="small" style={{ color: 'var(--fail)' }}>{badRows} row(s) have missing or invalid values or duplicate tags. They are reported individually and do not stop the valid rows.</p>}
        <div className="toolbar mt-16">
          <span className="small muted">Up to 200 feeders per run on the public site.</span>
          <span className="spacer" />
          {job ? (
            <>
              <div style={{ minWidth: 260 }}><ProgressBar done={job.done} total={job.total} label={job.total ? `${job.done} of ${job.total} feeders` : 'Queued…'} /></div>
              <button className="btn-outline" onClick={() => ctl.current?.abort()}>Cancel</button>
            </>
          ) : (
            <button className="btn-primary" onClick={runJob} disabled={!i.feeders.length || i.feeders.length > 200}>{c.busy ? <Spinner light /> : Icon.play} Calculate schedule</button>
          )}
        </div>
      </Panel>

      <ErrorBox error={c.error} />
      {c.run && (
        <div id="results" className="mt-16">
          <h2 className="section-title">Cable schedule</h2>
          <RunInfo run={c.run} outdated={c.outdated} onRecalc={runJob} busy={!!job} />
          <BatchResult inputs={c.payload} result={c.run.result} />
          <div className="mt-16"><VerificationNotice /></div>
          <div className="sticky-actions"><OutputBar mode="batch" inputs={c.payload} run={c.run} outdated={c.outdated} saved={c.saved} onSaved={c.setSaved} /></div>
        </div>
      )}
    </div>
  )
}
