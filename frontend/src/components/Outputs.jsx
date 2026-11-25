// Save / export bar shown under every result. Exports send the INPUTS to the
// server, which recomputes with the engine - a report can never contain
// numbers that the engine did not produce for those inputs.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { download, saveJson } from '../lib/api'
import { MODE_LABEL } from '../lib/format'
import { db, getPrefs, useStore } from '../lib/store'
import { Icon } from './icons'
import { ErrorBox, Field, Modal, Spinner } from './ui'

const SLIM_KEYS = ['detailed_options', 'spacing_variants', 'candidates', 'engine_messages']
/** Keep the stored result small enough for the browser: drop bulky option lists if huge. */
export function storableResult(result) {
  const s = JSON.stringify(result)
  if (s.length < 1_500_000) return result
  const slim = JSON.parse(s)
  for (const k of SLIM_KEYS) delete slim[k]
  if (Array.isArray(slim.rows)) slim.rows = slim.rows.map((r) => { const x = { ...r }; for (const k of SLIM_KEYS) delete x[k]; return x })
  slim._slimmed = true
  return slim
}

export function SaveModal({ mode, inputs, run, saved, onSaved, onClose }) {
  const { items: projects } = useStore('projects')
  const [title, setTitle] = useState(saved?.title || '')
  const [scenario, setScenario] = useState(saved?.scenario || 'Base case')
  const [projectId, setProjectId] = useState(saved?.projectId || '')
  const [newProject, setNewProject] = useState('')
  const [note, setNote] = useState('')
  const [asNew, setAsNew] = useState(!saved)
  const [err, setErr] = useState(null)

  async function save() {
    try {
      let pid = projectId
      if (pid === '__new') {
        if (!newProject.trim()) throw new Error('Enter a project name')
        pid = (await db.put('projects', { name: newProject.trim() })).id
      }
      const base = {
        mode, title: title.trim() || MODE_LABEL[mode], scenario: scenario.trim() || 'Base case', projectId: pid || null,
        inputs, result: run ? storableResult(run.result) : null, summary: run?.summary || null,
        engineVersion: run?.engine_version || null,
      }
      let rec
      if (saved && !asNew) {
        const history = [...(saved.history || []), { revision: saved.revision || 1, inputs: saved.inputs, summary: saved.summary, at: saved.updatedAt, engineVersion: saved.engineVersion, note: saved.note }]
        rec = await db.put('calculations', { ...saved, ...base, revision: (saved.revision || 1) + 1, history, note })
      } else {
        rec = await db.put('calculations', { ...base, revision: 1, history: [], note })
      }
      onSaved(rec)
    } catch (e) {
      setErr(e)
    }
  }
  return (
    <Modal title="Save to this browser" onClose={onClose}
      footer={<><button className="btn-outline" onClick={onClose}>Cancel</button><button className="btn-primary" onClick={save}>{Icon.save} Save</button></>}>
      <p className="small muted" style={{ marginTop: 0 }}>Saved in this browser only (IndexedDB) — not uploaded and not synchronised to other devices. Use Settings → Export to back it up.</p>
      <ErrorBox error={err} />
      <div className="form-grid" style={{ gridTemplateColumns: '1fr' }}>
        <Field label="Title"><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Pump P-101 feeder" maxLength={160} /></Field>
        <Field label="Scenario"><input value={scenario} onChange={(e) => setScenario(e.target.value)} maxLength={120} /></Field>
        <Field label="Project">
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">— none —</option>
            {(projects || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            <option value="__new">+ New project…</option>
          </select>
        </Field>
        {projectId === '__new' && <Field label="New project name"><input value={newProject} onChange={(e) => setNewProject(e.target.value)} /></Field>}
        <Field label="Revision note (optional)"><input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></Field>
        {saved && (
          <label className="inline-check"><input type="checkbox" checked={!asNew} onChange={(e) => setAsNew(!e.target.checked)} />
            Save as revision {(saved.revision || 1) + 1} of “{saved.title}” (previous inputs kept in its history)</label>
        )}
        {!run && <div className="notice notice-warn">{Icon.alert}<div>No result yet — the inputs are saved as a draft calculation.</div></div>}
      </div>
    </Modal>
  )
}

function ReportModal({ mode, inputs, title, onClose }) {
  const p = getPrefs().report
  const [meta, setMeta] = useState({ title: title || '', scenario: 'Base case', project_name: '', project_number: '', client: '', site: '', prepared_by: p.prepared_by, checked_by: p.checked_by, revision: '1', report_number: '' })
  const [kind, setKind] = useState(p.kind || 'detailed')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [done, setDone] = useState(null)
  const f = (k) => ({ value: meta[k], onChange: (e) => setMeta({ ...meta, [k]: e.target.value }) })
  async function go() {
    setBusy(true); setErr(null)
    try { setDone(await download('/outputs/report.pdf', { mode, inputs, meta, kind }, 'cable-n-report.pdf')) } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  return (
    <Modal title="PDF report" onClose={onClose} wide
      footer={<><button className="btn-outline" onClick={onClose}>Close</button><button className="btn-primary" onClick={go} disabled={busy}>{busy ? <Spinner light /> : Icon.download} Generate PDF</button></>}>
      <p className="small muted" style={{ marginTop: 0 }}>The server recalculates these inputs, builds the PDF in a temporary folder, sends it to you and deletes it. Text below is printed on the cover; leave fields blank to omit them.</p>
      <ErrorBox error={err} />
      {done && <div className="notice notice-good">{Icon.check}<div>Report {done.number} downloaded. Input fingerprint {done.hash?.slice(0, 16)}… — the same inputs always give the same fingerprint.</div></div>}
      <div className="form-grid mt-8">
        <Field label="Report title"><input {...f('title')} maxLength={160} /></Field>
        <Field label="Scenario"><input {...f('scenario')} maxLength={120} /></Field>
        <Field label="Project"><input {...f('project_name')} maxLength={160} /></Field>
        <Field label="Project number"><input {...f('project_number')} maxLength={60} /></Field>
        <Field label="Client"><input {...f('client')} maxLength={160} /></Field>
        <Field label="Site"><input {...f('site')} maxLength={160} /></Field>
        <Field label="Prepared by"><input {...f('prepared_by')} maxLength={120} /></Field>
        <Field label="Checked by"><input {...f('checked_by')} maxLength={120} /></Field>
        <Field label="Revision"><input {...f('revision')} maxLength={12} /></Field>
        <Field label="Report number" hint="Blank = generated from date + input fingerprint"><input {...f('report_number')} maxLength={40} /></Field>
        <Field label="Content">
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="detailed">Detailed — summary + full original engine report (diagrams, all options, references)</option>
            <option value="summary">Summary — cover, results, checks and warnings</option>
          </select>
        </Field>
      </div>
      <p className="small muted">No signatures or approval marks are added. Reports state that independent engineering verification is required.</p>
    </Modal>
  )
}

export function OutputBar({ mode, inputs, run, outdated, saved, onSaved, title }) {
  const [modal, setModal] = useState(null)
  const [busy, setBusy] = useState(null)
  const [err, setErr] = useState(null)
  const [savedMsg, setSavedMsg] = useState(null)
  async function exp(ext) {
    setBusy(ext); setErr(null)
    try { await download(`/outputs/export.${ext}`, { mode, inputs, meta: { title: title || '' } }, `cable-n.${ext}`) } catch (e) { setErr(e) } finally { setBusy(null) }
  }
  function json() {
    saveJson({ format: 'cable-n-calculation', version: 1, exportedAt: new Date().toISOString(),
      calculation: { mode, title: title || saved?.title || MODE_LABEL[mode], inputs, result: run?.result || null, summary: run?.summary || null, engineVersion: run?.engine_version || null } },
    `cable-n-${mode}.json`)
  }
  async function saveTemplate() {
    const name = window.prompt('Template name (stored in this browser):', saved?.title || '')
    if (!name) return
    await db.put('templates', { name: name.slice(0, 120), mode, inputs })
    setSavedMsg(`Template “${name}” saved.`)
  }
  const disabled = !run || outdated
  return (
    <>
      <div className="toolbar">
        <button className="btn-primary" onClick={() => setModal('save')}>{Icon.save} {saved ? 'Save' : 'Save to browser'}</button>
        <button className="btn-outline" onClick={() => setModal('report')} disabled={disabled} title={disabled ? 'Calculate first' : ''}>{Icon.file} PDF report</button>
        <button className="btn-outline" onClick={() => exp('xlsx')} disabled={disabled || !!busy}>{busy === 'xlsx' ? <Spinner /> : Icon.download} Excel</button>
        <button className="btn-outline" onClick={() => exp('csv')} disabled={disabled || !!busy}>{busy === 'csv' ? <Spinner /> : Icon.download} CSV</button>
        <button className="btn-outline" onClick={json}>{Icon.download} JSON</button>
        <button className="btn-sm" onClick={saveTemplate}>{Icon.copy} Save as template</button>
        <span className="spacer" />
        {saved && <span className="chip chip-brand">Saved · rev {saved.revision || 1}</span>}
      </div>
      {savedMsg && <div className="notice-ok mt-8">{savedMsg} <Link className="table-link" to="/calculators?tab=saved">Open saved work</Link></div>}
      <ErrorBox error={err} />
      {modal === 'save' && (
        <SaveModal mode={mode} inputs={inputs} run={run} saved={saved} onClose={() => setModal(null)}
          onSaved={(rec) => { setModal(null); onSaved?.(rec); setSavedMsg(`Saved “${rec.title}” (revision ${rec.revision}) in this browser.`) }} />
      )}
      {modal === 'report' && <ReportModal mode={mode} inputs={inputs} title={saved?.title || title} onClose={() => setModal(null)} />}
    </>
  )
}

/** Template picker + "use my defaults" for a calculator header. */
export function TemplatePicker({ mode, onApply }) {
  const { items } = useStore('templates')
  const list = (items || []).filter((t) => t.mode === mode)
  if (!list.length) return null
  return (
    <select className="btn-sm" style={{ paddingRight: 28 }} value="" onChange={(e) => { const t = list.find((x) => x.id === e.target.value); if (t) onApply(t.inputs) }} aria-label="Load template">
      <option value="">Load template…</option>
      {list.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
    </select>
  )
}
