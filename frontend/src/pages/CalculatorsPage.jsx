import { useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { WithRail } from '../components/Ads'
import { Icon } from '../components/icons'
import { EmptyState, ErrorBox, Notice, PageHeader, StatusBadge, Tabs } from '../components/ui'
import { saveJson } from '../lib/api'
import { MODE_LABEL, MODE_PATH, timeAgo } from '../lib/format'
import { db, importAll, useStore } from '../lib/store'
import { MODES } from './HomePage'

export default function CalculatorsPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || 'tools'
  const nav = useNavigate()
  const { items: calcs } = useStore('calculations')
  const { items: projects } = useStore('projects')
  const { items: templates } = useStore('templates')
  const [q, setQ] = useState('')
  const [mode, setMode] = useState('')
  const [proj, setProj] = useState(params.get('project') || '')
  const [sel, setSel] = useState(new Set())
  const [msg, setMsg] = useState(null)
  const fileRef = useRef(null)
  const pname = (id) => projects?.find((p) => p.id === id)?.name
  const list = useMemo(() => (calcs || []).filter((c) => (!mode || c.mode === mode) && (!proj || c.projectId === proj)
    && (!q || `${c.title} ${c.scenario} ${pname(c.projectId) || ''}`.toLowerCase().includes(q.toLowerCase()))), [calcs, mode, proj, q, projects]) // eslint-disable-line react-hooks/exhaustive-deps

  async function importFile(f) {
    try { const r = await importAll(JSON.parse(await f.text())); setMsg({ ok: true, text: `Imported: ${Object.entries(r).map(([k, v]) => `${v} ${k}`).join(', ')}` }) } catch (e) { setMsg({ ok: false, text: e.message }) }
  }
  async function duplicate(c) {
    const { id, createdAt, updatedAt, ...rest } = c
    await db.put('calculations', { ...rest, title: `${c.title} (copy)`, revision: 1, history: [] })
  }

  return (
    <WithRail>
      <PageHeader icon={Icon.calc} title="Calculators" hint="Four engineering calculators, plus everything you have saved in this browser." />
      <Tabs value={tab} onChange={(t) => setParams({ tab: t })} tabs={[
        { id: 'tools', label: 'Calculators' }, { id: 'saved', label: 'Saved calculations', badge: calcs?.length ?? 0 },
        { id: 'projects', label: 'Projects', badge: projects?.length ?? 0 }, { id: 'templates', label: 'Templates', badge: templates?.length ?? 0 }]} />

      {tab === 'tools' && (
        <div className="mode-grid">
          {MODES.map((m) => (
            <Link key={m.to} to={m.to} className="mode-card">
              <span className="mode-num">Mode {m.n}</span><h3>{m.title}</h3><p>{m.text}</p>
              <span className="mode-go">Open {Icon.arrowRight}</span>
            </Link>
          ))}
        </div>
      )}

      {tab !== 'tools' && <Notice tone="info">Saved work lives only in this browser on this device. It is not uploaded or synchronised — export a JSON backup to move it.</Notice>}
      {msg && <div className={msg.ok ? 'notice-ok mt-8' : 'error mt-8'}>{msg.text}</div>}

      {tab === 'saved' && (
        <div className="mt-16">
          <div className="filter-bar">
            <div className="search-field">{Icon.search}<input placeholder="Search title, scenario, project" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <select value={mode} onChange={(e) => setMode(e.target.value)}><option value="">All modes</option>{Object.entries(MODE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
            <select value={proj} onChange={(e) => setProj(e.target.value)}><option value="">All projects</option>{(projects || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
            <button className="btn-sm" onClick={() => fileRef.current?.click()}>{Icon.upload} Import JSON</button>
            <input ref={fileRef} type="file" accept=".json" hidden onChange={(e) => { if (e.target.files[0]) importFile(e.target.files[0]); e.target.value = '' }} />
            {sel.size >= 2 && <button className="btn-sm btn-sm-primary" onClick={() => nav(`/comparison?ids=${[...sel].join(',')}`)}>{Icon.compare} Compare ({sel.size})</button>}
          </div>
          {!list.length ? <EmptyState icon={Icon.save}>No saved calculations yet. Run a calculator and press “Save to browser”.</EmptyState> : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th /><th>Title</th><th>Mode</th><th>Project</th><th>Scenario</th><th>Result</th><th>Rev</th><th>Updated</th><th /></tr></thead>
                <tbody>
                  {list.map((c) => (
                    <tr key={c.id}>
                      <td><input type="checkbox" checked={sel.has(c.id)} onChange={(e) => { const s = new Set(sel); e.target.checked ? s.add(c.id) : s.delete(c.id); setSel(s) }} aria-label="Select" /></td>
                      <td><Link className="table-link" to={`/calculators/saved/${c.id}`}>{c.title}</Link></td>
                      <td>{MODE_LABEL[c.mode]}</td><td>{pname(c.projectId) || '—'}</td><td>{c.scenario}</td>
                      <td>{c.summary ? <StatusBadge status={c.summary.outcome} /> : <span className="muted small">draft</span>} {c.summary?.cable_size && <span className="small">{c.summary.cable_size}</span>}</td>
                      <td>{c.revision || 1}</td><td>{timeAgo(c.updatedAt)}</td>
                      <td className="row-actions">
                        <Link className="btn-sm" to={`${MODE_PATH[c.mode]}?load=${c.id}`}>{Icon.edit} Edit</Link>
                        <button className="btn-sm" onClick={() => duplicate(c)}>{Icon.copy}</button>
                        <button className="btn-sm" onClick={() => saveJson({ format: 'cable-n-calculation', version: 1, calculation: c }, `${c.title}.json`)}>{Icon.download}</button>
                        <button className="btn-sm btn-sm-danger" onClick={() => window.confirm(`Delete “${c.title}” from this browser?`) && db.remove('calculations', c.id)}>{Icon.trash}</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'projects' && <Projects projects={projects || []} calcs={calcs || []} />}

      {tab === 'templates' && (
        <div className="mt-16">
          {!templates?.length ? <EmptyState icon={Icon.copy}>No templates. In any calculator, press “Save as template” to reuse its inputs.</EmptyState> : (
            <ul className="mini-list panel">
              {templates.map((t) => (
                <li key={t.id} className="mini-row" style={{ cursor: 'default' }}>
                  <span className="mini-icon tone-brand">{Icon.copy}</span>
                  <div className="mini-main"><div className="mini-title">{t.name}</div><div className="mini-sub">{MODE_LABEL[t.mode]} · {timeAgo(t.updatedAt)}</div></div>
                  <div className="row-actions">
                    <Link className="btn-sm btn-sm-primary" to={`${MODE_PATH[t.mode]}?template=${t.id}`}>Use</Link>
                    <button className="btn-sm btn-sm-danger" onClick={() => db.remove('templates', t.id)}>{Icon.trash}</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </WithRail>
  )
}

function Projects({ projects, calcs }) {
  const [edit, setEdit] = useState(null)
  const [err, setErr] = useState(null)
  async function save() {
    if (!edit.name?.trim()) return setErr({ message: 'Project name is required' })
    await db.put('projects', edit); setEdit(null); setErr(null)
  }
  const f = (k) => ({ value: edit[k] || '', onChange: (e) => setEdit({ ...edit, [k]: e.target.value }) })
  return (
    <div className="mt-16">
      <div className="toolbar mb-16"><button className="btn-primary" onClick={() => setEdit({ name: '', status: 'active' })}>{Icon.plus} New project</button></div>
      {edit && (
        <div className="card mb-16">
          <ErrorBox error={err} />
          <div className="form-grid">
            {[['name', 'Project name'], ['number', 'Project number'], ['client', 'Client'], ['site', 'Site'], ['engineer', 'Engineer'], ['reviewer', 'Reviewer']].map(([k, l]) => <label key={k}>{l}<input {...f(k)} maxLength={160} /></label>)}
            <label>Status<select {...f('status')}><option value="active">Active</option><option value="on_hold">On hold</option><option value="completed">Completed</option><option value="archived">Archived</option></select></label>
            <label style={{ gridColumn: '1/-1' }}>Requirements / notes<textarea rows={3} {...f('notes')} /></label>
          </div>
          <div className="row-actions mt-16"><button className="btn-primary" onClick={save}>Save project</button><button className="btn-outline" onClick={() => setEdit(null)}>Cancel</button></div>
        </div>
      )}
      {!projects.length ? <EmptyState icon={Icon.file}>No projects yet. Projects group saved calculations and their scenarios.</EmptyState> : (
        <div className="mode-grid">
          {projects.map((p) => {
            const cs = calcs.filter((c) => c.projectId === p.id)
            return (
              <div key={p.id} className="mode-card" style={{ cursor: 'default' }}>
                <span className="mode-num">{p.number || 'Project'} · {p.status || 'active'}</span>
                <h3>{p.name}</h3>
                <p>{[p.client, p.site].filter(Boolean).join(' · ') || 'No client / site'}<br />{cs.length} calculation(s){cs.length ? `: ${cs.slice(0, 3).map((c) => c.title).join(', ')}${cs.length > 3 ? '…' : ''}` : ''}</p>
                <div className="row-actions">
                  <Link className="btn-sm" to={`/calculators?tab=saved&project=${p.id}`}>Calculations</Link>
                  <button className="btn-sm" onClick={() => setEdit(p)}>{Icon.edit} Edit</button>
                  <button className="btn-sm" onClick={() => saveJson({ format: 'cable-n-export', version: 1, projects: [p], calculations: cs, templates: [], cables: [] }, `${p.name}.json`)}>{Icon.download} Export</button>
                  <button className="btn-sm btn-sm-danger" onClick={() => window.confirm(`Delete project “${p.name}”? Its calculations are kept, unassigned.`) && db.remove('projects', p.id)}>{Icon.trash}</button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
