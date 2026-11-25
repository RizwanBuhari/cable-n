import { useEffect, useRef, useState } from 'react'
import { openConsent } from '../components/Consent'
import { Icon } from '../components/icons'
import { ErrorBox, Field, KV, NumInput, PageHeader } from '../components/ui'
import { api, saveJson } from '../lib/api'
import { bytes } from '../lib/format'
import { ACCENT_SWATCHES, ADS, applyAccentColor, getConsent, getLicence, getStoredAccentId, setLicence } from '../lib/prefs'
import { clearAll, exportAll, getPrefs, importAll, setPrefs, storageEstimate } from '../lib/store'

export default function SettingsPage() {
  const [accent, setAccent] = useState(getStoredAccentId)
  const [prefs, setP] = useState(getPrefs)
  const [saved, setSaved] = useState(false)
  const [health, setHealth] = useState(null)
  const [est, setEst] = useState(null)
  const [msg, setMsg] = useState(null)
  const [key, setKey] = useState('')
  const [lic, setLic] = useState(getLicence)
  const [err, setErr] = useState(null)
  const fileRef = useRef(null)
  useEffect(() => { api('/health').then(setHealth).catch(() => {}); storageEstimate().then(setEst) }, [])
  const e = prefs.engineering
  const setE = (k, v) => { setP({ ...prefs, engineering: { ...e, [k]: v } }); setSaved(false) }
  const setR = (k, v) => { setP({ ...prefs, report: { ...prefs.report, [k]: v } }); setSaved(false) }

  async function verify() {
    setErr(null)
    try { const r = await api('/premium/verify', { method: 'POST', body: { key } }); setLicence(r); setLic(r); setKey('') } catch (x) { setErr(x) }
  }

  return (
    <div className="section-gap">
      <PageHeader icon={Icon.settings} title="Settings" hint="Stored in this browser only." />
      <div className="card settings-section">
        <h3>Appearance</h3>
        <p className="section-hint">Accent colour for your view. Engineering status colours (pass, fail, warning) never change.</p>
        <div className="accent-swatch-row">
          {ACCENT_SWATCHES.map((s) => (
            <button key={s.id} type="button" className={`accent-swatch ${accent === s.id ? 'accent-swatch-active' : ''}`} style={{ background: s.base }} title={s.label} aria-label={s.label}
              onClick={() => { applyAccentColor(s.id); setAccent(s.id) }}>{accent === s.id && Icon.check}</button>
          ))}
        </div>
      </div>
      <div className="card settings-section">
        <h3>Engineering defaults</h3>
        <p className="section-hint">Pre-fill new calculations. They are always visible and editable in each form — nothing is applied silently.</p>
        <div className="form-grid">
          <Field label="Voltage-drop limit" unit="%"><NumInput value={e.voltage_drop_limit_pct} onChange={(v) => setE('voltage_drop_limit_pct', v)} /></Field>
          <Field label="Power factor"><NumInput value={e.power_factor} onChange={(v) => setE('power_factor', v)} /></Field>
          <Field label="Soil temperature" unit="°C"><NumInput value={e.soil_temp} onChange={(v) => setE('soil_temp', v)} /></Field>
          <Field label="Air temperature" unit="°C"><NumInput value={e.air_temp} onChange={(v) => setE('air_temp', v)} /></Field>
          <Field label="Soil resistivity" unit="K·m/W"><NumInput value={e.soil_resistivity} onChange={(v) => setE('soil_resistivity', v)} /></Field>
          <Field label="Duct resistivity" unit="K·m/W"><NumInput value={e.duct_resistivity} onChange={(v) => setE('duct_resistivity', v)} /></Field>
          <Field label="Burial depth" unit="m"><NumInput value={e.depth} onChange={(v) => setE('depth', v)} /></Field>
          <Field label="Fault clearing time" unit="s"><NumInput value={e.fault_time} onChange={(v) => setE('fault_time', v)} /></Field>
          <Field label="Fault sharing"><select value={e.fault_share} onChange={(ev) => setE('fault_share', ev.target.value)}><option value="equal">Equal sharing</option><option value="full">Full fault per cable</option></select></Field>
        </div>
        <h3 className="mt-16">Report defaults</h3>
        <div className="form-grid">
          <Field label="Prepared by"><input value={prefs.report.prepared_by} onChange={(ev) => setR('prepared_by', ev.target.value)} /></Field>
          <Field label="Checked by"><input value={prefs.report.checked_by} onChange={(ev) => setR('checked_by', ev.target.value)} /></Field>
          <Field label="Default content"><select value={prefs.report.kind} onChange={(ev) => setR('kind', ev.target.value)}><option value="detailed">Detailed</option><option value="summary">Summary</option></select></Field>
        </div>
        <div className="row-actions mt-16"><button className="btn-primary" onClick={() => { setPrefs(prefs); setSaved(true) }}>Save defaults</button>{saved && <span className="notice-ok">Saved</span>}</div>
      </div>
      <div className="card settings-section">
        <h3>Your data in this browser</h3>
        <p className="section-hint">Saved calculations, projects, templates and custom cables never leave this browser unless you export them. They are not synchronised across devices, and clearing site data in your browser deletes them.</p>
        {est && <p className="small">Storage used: {bytes(est.used)} of about {bytes(est.quota)} available.</p>}
        {msg && <div className={msg.ok ? 'notice-ok mb-16' : 'error mb-16'}>{msg.text}</div>}
        <div className="row-actions">
          <button className="btn-outline" onClick={async () => saveJson(await exportAll(), `cable-n-backup-${new Date().toISOString().slice(0, 10)}.json`)}>{Icon.download} Export everything (JSON)</button>
          <button className="btn-outline" onClick={() => fileRef.current?.click()}>{Icon.upload} Import backup</button>
          <input ref={fileRef} type="file" accept=".json" hidden onChange={async (ev) => { const f = ev.target.files[0]; ev.target.value = ''; if (!f) return; try { const r = await importAll(JSON.parse(await f.text())); setMsg({ ok: true, text: `Imported ${Object.entries(r).map(([k, v]) => `${v} ${k}`).join(', ')}.` }) } catch (x) { setMsg({ ok: false, text: x.message }) } }} />
          <button className="btn-outline" style={{ color: 'var(--fail)' }} onClick={async () => { if (window.confirm('Delete ALL saved calculations, projects, templates, custom cables, drafts and preferences from this browser? This cannot be undone.')) { await clearAll(); setMsg({ ok: true, text: 'All local data cleared.' }) } }}>{Icon.trash} Clear all local data</button>
        </div>
      </div>
      <div className="card settings-section">
        <h3>Privacy & cookies</h3>
        <p className="section-hint">{ADS.enabled ? `Advertising: ${getConsent()?.ads ? 'allowed' : 'not allowed'}${ADS.cmp === 'google' ? ' (managed by Google\'s consent message)' : ''}.` : 'This site shows no advertising and sets no tracking cookies.'}</p>
        <button className="btn-outline" onClick={openConsent}>{Icon.cookie} Change cookie preferences</button>
      </div>
      {health?.premium_enabled && (
        <div className="card settings-section">
          <h3>Ad-free licence</h3>
          {lic?.ad_free ? <p className="notice-ok">Ad-free active{lic.expires ? ` until ${lic.expires}` : ''}. <button className="table-link" style={{ border: 0, background: 'none' }} onClick={() => { setLicence(null); setLic(null) }}>Remove</button></p> : (
            <><ErrorBox error={err} /><div className="row-actions"><input style={{ flex: 1, minWidth: 260 }} placeholder="CN1.…" value={key} onChange={(ev) => setKey(ev.target.value)} /><button className="btn-primary" onClick={verify} disabled={!key}>Activate</button></div></>
          )}
        </div>
      )}
      <div className="card settings-section">
        <h3>System</h3>
        <KV rows={[['Calculation engine', health?.engine_version || '…'], ['Engine status', health ? (health.engine_ok ? 'online' : 'unavailable') : '…'], ['Original program fingerprint', health?.original_sha256],
          ['AI assistant', health ? (health.ai_configured ? 'enabled' : 'not enabled on this site') : '…'], ['Accounts / server database', 'none — the server stores nothing you calculate']]} />
      </div>
    </div>
  )
}
