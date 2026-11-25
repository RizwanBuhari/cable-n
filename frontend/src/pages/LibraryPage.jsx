import { useEffect, useMemo, useRef, useState } from 'react'
import { WithRail } from '../components/Ads'
import { Icon } from '../components/icons'
import { ErrorBox, Field, KV, Modal, Notice, NumInput, PageHeader, Spinner, StatusBadge, Tabs } from '../components/ui'
import { api, saveJson } from '../lib/api'
import { num } from '../lib/format'
import { db, useStore } from '../lib/store'
import { DataTable } from '../results/common'

const blank = { code: '', manufacturer: '', cable_type: '', voltage_kv: null, material: 'CU', size_mm2: null, cores: 1, insulation: 'XLPE', armour: '', R_ohm_per_km: null, X_ohm_per_km: null, rating_A: null, data_source: '', revision: 'A', mode4_json: '' }

export default function LibraryPage() {
  const [lib, setLib] = useState(null)
  const [err, setErr] = useState(null)
  const { items: custom } = useStore('cables')
  const [tab, setTab] = useState('builtin')
  const [q, setQ] = useState('')
  const [mat, setMat] = useState('')
  const [cores, setCores] = useState('')
  const [open, setOpen] = useState(null)
  const [cmp, setCmp] = useState([])
  const [edit, setEdit] = useState(null)
  const [extract, setExtract] = useState(null)
  useEffect(() => { api('/cable-library').then(setLib).catch(setErr) }, [])
  const rows = useMemo(() => {
    const base = tab === 'builtin' ? (lib?.records || []) : (custom || []).map((c) => ({ ...c, source_kind: 'custom' }))
    return base.filter((r) => (!mat || r.material === mat) && (!cores || String(r.cores) === cores) && (!q || `${r.code} ${r.cable_type} ${r.manufacturer || ''}`.toLowerCase().includes(q.toLowerCase())))
  }, [lib, custom, tab, q, mat, cores])
  const toggle = (r) => setCmp((c) => (c.find((x) => x.id === r.id) ? c.filter((x) => x.id !== r.id) : c.length < 4 ? [...c, r] : c))

  return (
    <WithRail>
      <PageHeader icon={Icon.cable} title="Cable library" hint="Built-in tables used by the engine, illustrative MV/HV presets, and your own cable definitions (kept in this browser)." />
      <Notice tone="info">{lib?.notice || 'Generic table data — not any manufacturer\'s product data.'} Custom cables are unverified until you check them against the datasheet.</Notice>
      <ErrorBox error={err} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'builtin', label: 'Built-in & presets', badge: lib?.records.length }, { id: 'custom', label: 'My cables', badge: custom?.length ?? 0 }]} />
      <div className="filter-bar">
        <div className="search-field">{Icon.search}<input placeholder="Search code or type" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select value={mat} onChange={(e) => setMat(e.target.value)}><option value="">Cu & Al</option><option value="CU">Copper</option><option value="AL">Aluminium</option></select>
        <select value={cores} onChange={(e) => setCores(e.target.value)}><option value="">Any cores</option><option value="1">Single-core</option><option value="3">Three-core</option></select>
        {tab === 'custom' && (
          <>
            <button className="btn-sm btn-sm-primary" onClick={() => setEdit({ ...blank })}>{Icon.plus} Add cable</button>
            <button className="btn-sm" onClick={() => setExtract({})}>{Icon.file} From datasheet PDF</button>
            <button className="btn-sm" onClick={() => saveJson({ format: 'cable-n-export', version: 1, cables: custom || [] }, 'cable-n-my-cables.json')}>{Icon.download} Export</button>
          </>
        )}
        {cmp.length >= 2 && <button className="btn-sm btn-sm-primary" onClick={() => setOpen({ compare: true })}>{Icon.compare} Compare {cmp.length}</button>}
      </div>
      {!lib && tab === 'builtin' ? <Spinner /> : (
        <DataTable rows={rows} rowKey={(r) => r.id} onRow={(r) => setOpen(r)} columns={[
          { key: 'sel', label: '', sortable: false, render: (r) => <input type="checkbox" checked={!!cmp.find((x) => x.id === r.id)} onClick={(e) => e.stopPropagation()} onChange={() => toggle(r)} aria-label="Compare" /> },
          { key: 'code', label: 'Code' }, { key: 'cable_type', label: 'Type' }, { key: 'material', label: 'Mat.' },
          { key: 'size_mm2', label: 'mm²', num: true }, { key: 'cores', label: 'Cores', num: true }, { key: 'armour', label: 'Armour' },
          { key: 'R', label: 'R Ω/km', num: true, sortValue: (r) => r.data?.R_ohm_per_km ?? r.R_ohm_per_km, render: (r) => num(r.data?.R_ohm_per_km ?? r.R_ohm_per_km, 4) },
          { key: 'X', label: 'X Ω/km', num: true, sortValue: (r) => r.data?.X_ohm_per_km ?? r.X_ohm_per_km, render: (r) => num(r.data?.X_ohm_per_km ?? r.X_ohm_per_km, 3) },
          { key: 'source_kind', label: 'Source', render: (r) => <span className="chip">{r.source_kind}</span> },
          { key: 'review_status', label: 'Status', render: (r) => <StatusBadge status={r.review_status === 'approved' ? 'OK' : 'WARNING'} label={r.review_status === 'approved' ? 'engine table' : r.review_status || 'unverified'} /> },
        ]} />
      )}
      {open && !open.compare && (
        <Modal title={open.code} onClose={() => setOpen(null)} wide footer={open.source_kind === 'custom' && (
          <><button className="btn-sm btn-sm-danger" onClick={() => { db.remove('cables', open.id); setOpen(null) }}>{Icon.trash} Delete</button><button className="btn-primary" onClick={() => { setEdit({ ...blank, ...open, mode4_json: open.data?.mode4_cable ? JSON.stringify(open.data.mode4_cable, null, 2) : '' }); setOpen(null) }}>{Icon.edit} Edit</button></>
        )}>
          <KV rows={[['Type', open.cable_type], ['Manufacturer', open.manufacturer || '—'], ['Material / size / cores', `${open.material} · ${open.size_mm2 ?? '—'} mm² · ${open.cores}`],
            ['Insulation / armour', `${open.insulation} / ${open.armour || '—'}`], ['Rated voltage', open.voltage_kv ? `${open.voltage_kv} kV` : '—'], ['Data source', open.data_source], ['Revision', open.revision]]} />
          {open.data?.base_ratings_A && (
            <>
              <h4>Base current ratings (A) by arrangement</h4>
              <KV rows={Object.entries(open.data.base_ratings_A).map(([k, v]) => [k, v ?? 'not tabled'])} />
              <p className="small muted">{open.data.notes} 20 °C DC resistance (IEC 60228): {open.data.R0_20C_ohm_per_km ?? '—'} Ω/km.</p>
            </>
          )}
          {open.data?.mode4_cable && <><h4>Mode 4 definition</h4><pre className="mono small">{JSON.stringify(open.data.mode4_cable, null, 2)}</pre><p className="small muted">Use it from the Advanced MV/HV calculator → “Add from preset / library”.</p></>}
        </Modal>
      )}
      {open?.compare && (
        <Modal title="Compare cables" onClose={() => setOpen(null)} wide>
          <div className="table-scroll"><table className="data-table"><tbody>
            {[['Code', (r) => r.code], ['Material', (r) => r.material], ['Size mm²', (r) => r.size_mm2], ['Cores', (r) => r.cores], ['Armour', (r) => r.armour || '—'],
              ['R Ω/km', (r) => num(r.data?.R_ohm_per_km ?? r.R_ohm_per_km, 4)], ['X Ω/km', (r) => num(r.data?.X_ohm_per_km ?? r.X_ohm_per_km, 3)],
              ...Object.keys(cmp[0].data?.base_ratings_A || {}).map((k) => [k, (r) => r.data?.base_ratings_A?.[k] ?? '—']), ['Source', (r) => r.source_kind]].map(([l, fn]) => (
              <tr key={l}><th>{l}</th>{cmp.map((r) => <td key={r.id}>{fn(r)}</td>)}</tr>
            ))}
          </tbody></table></div>
          <p className="small muted">Side-by-side data only — no cable is ranked as better overall.</p>
        </Modal>
      )}
      {edit && <EditModal value={edit} onClose={() => setEdit(null)} />}
      {extract && <ExtractModal onClose={() => setExtract(null)} onUse={(v) => { setExtract(null); setEdit({ ...blank, ...v }) }} />}
    </WithRail>
  )
}

function EditModal({ value, onClose }) {
  const [v, setV] = useState(value)
  const [err, setErr] = useState(null)
  const f = (k) => ({ value: v[k] ?? '', onChange: (e) => setV({ ...v, [k]: e.target.value }) })
  const n = (k) => ({ value: v[k], onChange: (x) => setV({ ...v, [k]: x }) })
  async function save() {
    try {
      if (!v.code.trim()) throw new Error('Code is required')
      if (v.data_source.trim().length < 3) throw new Error('A data source (datasheet, page, revision) is required')
      let mode4 = null
      if (v.mode4_json.trim()) {
        mode4 = JSON.parse(v.mode4_json)
        await api('/calculations/advanced-mvhv/cable-preview', { method: 'POST', body: { cable: mode4 } })
      }
      const { mode4_json, ...rest } = v
      await db.put('cables', { ...rest, review_status: 'unverified', data: { R_ohm_per_km: v.R_ohm_per_km, X_ohm_per_km: v.X_ohm_per_km, rating_A: v.rating_A, ...(mode4 ? { mode4_cable: mode4 } : {}) } })
      onClose()
    } catch (e) { setErr(e instanceof SyntaxError ? new Error('Mode 4 definition is not valid JSON') : e) }
  }
  return (
    <Modal title={v.id ? `Edit ${v.code}` : 'Add custom cable'} onClose={onClose} wide footer={<><button className="btn-outline" onClick={onClose}>Cancel</button><button className="btn-primary" onClick={save}>Save in this browser</button></>}>
      <ErrorBox error={err} />
      <div className="form-grid">
        <Field label="Code"><input {...f('code')} /></Field><Field label="Manufacturer"><input {...f('manufacturer')} /></Field>
        <Field label="Cable type"><input {...f('cable_type')} /></Field><Field label="Rated voltage" unit="kV"><NumInput {...n('voltage_kv')} /></Field>
        <Field label="Material"><select {...f('material')}><option value="CU">Copper</option><option value="AL">Aluminium</option></select></Field>
        <Field label="Size" unit="mm²"><NumInput {...n('size_mm2')} /></Field><Field label="Cores"><NumInput {...n('cores')} step={1} /></Field>
        <Field label="Insulation"><input {...f('insulation')} /></Field><Field label="Armour"><input {...f('armour')} /></Field>
        <Field label="R (AC, operating)" unit="Ω/km"><NumInput {...n('R_ohm_per_km')} /></Field><Field label="X" unit="Ω/km"><NumInput {...n('X_ohm_per_km')} /></Field>
        <Field label="Datasheet rating" unit="A"><NumInput {...n('rating_A')} /></Field><Field label="Revision"><input {...f('revision')} /></Field>
        <Field label="Data source (required)" wide hint="Datasheet name, revision and page"><input {...f('data_source')} /></Field>
        <Field label="Mode 4 cable definition (optional JSON)" wide hint="Same fields as the Advanced calculator cable editor; checked by the engine on save"><textarea rows={5} {...f('mode4_json')} className="mono" /></Field>
      </div>
      <p className="small muted">Custom data is stored in this browser only and is marked unverified. The engine's built-in tables are not changed by it.</p>
    </Modal>
  )
}

function ExtractModal({ onClose, onUse }) {
  const ref = useRef(null)
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [pick, setPick] = useState({})
  async function upload(file) {
    setBusy(true); setErr(null)
    const fd = new FormData(); fd.append('file', file)
    try { setRes(await api('/cable-library/extract-datasheet', { method: 'POST', form: fd })) } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const fields = res ? [...new Set(res.candidates.map((c) => c.field))] : []
  const map = { size_mm2: 'size_mm2', voltage_kv: 'voltage_kv', rating_A: 'rating_A' }
  return (
    <Modal title="Extract from datasheet PDF" onClose={onClose} wide footer={res && <button className="btn-primary" onClick={() => onUse({ ...Object.fromEntries(Object.entries(pick).filter(([k]) => map[k]).map(([k, c]) => [map[k], c.value])), material: res.hints.material || 'CU', insulation: res.hints.insulation || 'XLPE', armour: res.hints.armour || '', data_source: `${res.filename}: ${Object.values(pick).map((c) => `${c.field} p.${c.page}`).join(', ')}` })}>Use verified values</button>}>
      <Notice>Conventional text extraction (no AI). The PDF is processed in memory and discarded. Every value must be checked against the page shown before use.</Notice>
      <div className="toolbar mt-8"><button className="btn-outline" onClick={() => ref.current?.click()} disabled={busy}>{busy ? <Spinner /> : Icon.upload} Choose PDF</button><input ref={ref} type="file" accept="application/pdf" hidden onChange={(e) => e.target.files[0] && upload(e.target.files[0])} /></div>
      <ErrorBox error={err} />
      {res && !res.text_found && <Notice tone="alert">No text found — the PDF may be scanned. Enter values manually.</Notice>}
      {fields.map((fld) => (
        <div key={fld} className="mt-16">
          <h4 style={{ margin: '0 0 6px' }}>{fld}</h4>
          {res.candidates.filter((c) => c.field === fld).map((c, k) => (
            <label key={k} className="inline-check" style={{ alignItems: 'flex-start', marginBottom: 6 }}>
              <input type="radio" name={fld} checked={pick[fld] === c} onChange={() => setPick({ ...pick, [fld]: c })} />
              <span><b>{c.value}</b> <span className="chip">page {c.page}</span> <span className="small muted">…{c.context}…</span></span>
            </label>
          ))}
        </div>
      ))}
    </Modal>
  )
}
