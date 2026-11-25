import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from '../components/icons'
import { OutputBar, TemplatePicker } from '../components/Outputs'
import { useShareableCalc } from '../components/ChatPanel'
import { Choice, ErrorBox, Field, KV, NumInput, PageHeader, Panel, Spinner, Stepper, Toggle, VerificationNotice } from '../components/ui'
import { api } from '../lib/api'
import { getPrefs } from '../lib/store'
import { useCalculator } from '../lib/useCalculator'
import { RunInfo } from '../results/common'
import SingleFeederResult from '../results/SingleFeederResult'

const STEPS = ['Electrical system', 'Cable construction', 'Installation', 'Short circuit', 'Review & calculate']

export function defaults() {
  const e = getPrefs().engineering
  return {
    voltage: 415, voltage_drop_limit_pct: e.voltage_drop_limit_pct, power_factor: e.power_factor, phase: 'three',
    load_mode: 'current', current: 250, power: 150, power_unit: 'KW',
    insulation: 'xlpe', core_type: '3C', armored: true, material: 'cu',
    installation: 'buried', soil_resistivity: e.soil_resistivity, duct_resistivity: e.duct_resistivity, soil_temp: e.soil_temp,
    depth: e.depth, air_temp: e.air_temp, cable_length: 150, arrangement: null,
    sc_check: false, fault_kA: 25, fault_time: e.fault_time, fault_share: e.fault_share,
  }
}

export function payloadOf(i) {
  const p = {
    voltage: i.voltage, voltage_drop_limit_pct: i.voltage_drop_limit_pct, power_factor: i.power_factor, phase: i.phase,
    load_mode: i.load_mode, insulation: i.insulation, core_type: i.core_type, armored: i.armored, material: i.material,
    installation: i.installation, cable_length: i.cable_length, sc_check: i.sc_check, arrangement: i.arrangement || null,
  }
  if (i.load_mode === 'current') p.current = i.current
  else Object.assign(p, { power: i.power, power_unit: i.power_unit })
  if (i.installation === 'buried') Object.assign(p, { soil_resistivity: i.soil_resistivity, soil_temp: i.soil_temp, depth: i.depth })
  if (i.installation === 'duct') Object.assign(p, { duct_resistivity: i.duct_resistivity, soil_temp: i.soil_temp, depth: i.depth })
  if (i.installation === 'air') p.air_temp = i.air_temp
  if (i.sc_check) Object.assign(p, { fault_kA: i.fault_kA, fault_time: i.fault_time, fault_share: i.fault_share })
  return p
}

function stepErrors(step, i) {
  const e = {}
  const pos = (k, label) => { if (!(i[k] > 0)) e[k] = `${label} must be greater than 0` }
  if (step === 0) {
    pos('voltage', 'Voltage')
    if (!(i.voltage_drop_limit_pct >= 0 && i.voltage_drop_limit_pct <= 100)) e.voltage_drop_limit_pct = '0–100 %'
    if (!(i.power_factor >= 0 && i.power_factor <= 1)) e.power_factor = 'Between 0 and 1'
    if (i.load_mode === 'current') pos('current', 'Current')
    else {
      pos('power', 'Power')
      if (['KW', 'MW'].includes(i.power_unit) && !(i.power_factor > 0)) e.power_factor = 'Must be > 0 for kW / MW loads (divisor)'
    }
  }
  if (step === 2) {
    pos('cable_length', 'Length')
    const tmax = i.insulation === 'pvc' ? 70 : 90
    if (i.installation === 'air') {
      if (!(i.air_temp >= -50 && i.air_temp < tmax)) e.air_temp = `−50 to below ${tmax} °C (conductor limit)`
    } else {
      if (!(i.soil_temp >= -50 && i.soil_temp < tmax)) e.soil_temp = `−50 to below ${tmax} °C (conductor limit)`
      if (!(i.depth >= 0.1 && i.depth <= 3)) e.depth = '0.1–3.0 m'
      const k = i.installation === 'buried' ? 'soil_resistivity' : 'duct_resistivity'
      if (!(i[k] >= 0.1)) e[k] = 'At least 0.1 K·m/W'
    }
  }
  if (step === 3 && i.sc_check) {
    if (!(i.fault_kA >= 0.01)) e.fault_kA = 'At least 0.01 kA'
    if (!(i.fault_time >= 0.01 && i.fault_time <= 5)) e.fault_time = '0.01–5 s'
  }
  return e
}

export default function SingleFeederPage() {
  const c = useCalculator('single_feeder', defaults, payloadOf)
  const { inputs: i, set } = c
  const [step, setStep] = useState(0)
  const [maxStep, setMaxStep] = useState(c.run ? 4 : 0)
  const [arrs, setArrs] = useState([])
  const errs = stepErrors(step, i)
  const errCount = Object.keys(errs).length
  useShareableCalc(c.run && !c.outdated ? { mode: 'single_feeder', inputs: c.payload, label: 'single feeder' } : null)

  useEffect(() => {
    let live = true
    api('/calculations/single-feeder/arrangements', { method: 'POST', body: { material: i.material, armored: i.armored, core_type: i.core_type, installation: i.installation } })
      .then((a) => {
        if (!live) return
        setArrs(a)
        if (!a.some((x) => x.key === i.arrangement)) set({ arrangement: a[0]?.key || null })
      })
      .catch(() => live && setArrs([]))
    return () => { live = false }
  }, [i.material, i.armored, i.core_type, i.installation]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (c.run) setMaxStep(4) }, [c.run])

  const go = (n) => { setStep(n); setMaxStep((m) => Math.max(m, n)) }
  const next = () => errCount === 0 && go(Math.min(step + 1, 4))
  const f = (k) => ({ value: i[k], onChange: (v) => set({ [k]: v }) })
  const E = (k) => errs[k]
  const allErrors = [0, 2, 3].flatMap((s) => Object.values(stepErrors(s, i)))
  const arrLabel = arrs.find((a) => a.key === i.arrangement)?.label

  async function calculate() {
    const r = await c.execute()
    if (r) setTimeout(() => document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' }), 50)
  }

  return (
    <div>
      <PageHeader icon={Icon.cable} title="Single feeder sizing" hint="Mode 1 — size one feeder: ampacity with correction factors, voltage drop, short-circuit withstand and every single- and parallel-run option."
        actions={<><TemplatePicker mode="single_feeder" onApply={c.loadPayload} /><button className="btn-sm" onClick={c.reset}>{Icon.refresh} New</button></>} />
      {c.restoredDraft && <div className="notice notice-info mb-16">{Icon.info}<div>Your previous unsaved inputs were restored from this browser. <button className="table-link" style={{ border: 0, background: 'none', cursor: 'pointer' }} onClick={c.reset}>Start fresh</button></div></div>}
      {c.saved && <div className="notice notice-info mb-16">{Icon.save}<div>Editing saved calculation “{c.saved.title}” (revision {c.saved.revision || 1}).</div></div>}

      <Stepper steps={STEPS} current={step} onStep={go} maxReached={maxStep} />
      <Panel>
        {step === 0 && (
          <div className="form-section">
            <h3>Electrical system</h3>
            <p>System voltage is the line voltage for three-phase and the phase voltage for single-phase systems.</p>
            <div className="form-grid">
              <Field label="System phases"><select value={i.phase} onChange={(e) => set({ phase: e.target.value })}><option value="three">Three-phase</option><option value="single">Single-phase</option></select></Field>
              <Field label="System voltage" unit="V" error={E('voltage')}><NumInput {...f('voltage')} min={1} /></Field>
              <Field label="Maximum voltage drop" unit="%" error={E('voltage_drop_limit_pct')} tip="Entered as a percentage (e.g. 5 for 5 %) — converted to a fraction internally."><NumInput {...f('voltage_drop_limit_pct')} min={0} max={100} /></Field>
              <Field label="Power factor" error={E('power_factor')} hint="cos φ, 0–1"><NumInput {...f('power_factor')} min={0} max={1} step={0.01} /></Field>
            </div>
            <div className="form-section">
              <h3>Load</h3>
              <Choice value={i.load_mode} onChange={(v) => set({ load_mode: v })} options={[{ value: 'current', label: 'Load current', hint: 'Enter the design current directly' }, { value: 'power', label: 'Load power', hint: 'kW, kVA, MW or MVA' }]} />
              <div className="form-grid mt-16">
                {i.load_mode === 'current' ? (
                  <Field label="Design current Ib" unit="A" error={E('current')}><NumInput {...f('current')} min={0} /></Field>
                ) : (
                  <>
                    <Field label="Power" error={E('power')}><NumInput {...f('power')} min={0} /></Field>
                    <Field label="Unit" hint={['KW', 'MW'].includes(i.power_unit) ? 'Real power: divided by power factor' : 'Apparent power: power factor not used for Ib'}>
                      <select value={i.power_unit} onChange={(e) => set({ power_unit: e.target.value })}><option value="KW">kW</option><option value="KVA">kVA</option><option value="MW">MW</option><option value="MVA">MVA</option></select>
                    </Field>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="form-section">
            <h3>Cable construction</h3>
            <p>The base ampacity tables are 90 °C XLPE ratings. PVC uses an approximate correction (disclosed in the results).</p>
            <div className="form-grid">
              <Field label="Conductor"><Choice value={i.material} onChange={(v) => set({ material: v })} options={[{ value: 'cu', label: 'Copper' }, { value: 'al', label: 'Aluminium' }]} /></Field>
              <Field label="Cores"><Choice value={i.core_type} onChange={(v) => set({ core_type: v })} options={[{ value: '1C', label: 'Single-core', hint: '3 cables per circuit' }, { value: '3C', label: 'Three-core' }]} /></Field>
              <Field label="Armour"><Choice value={i.armored} onChange={(v) => set({ armored: v })} options={[{ value: true, label: 'Armoured' }, { value: false, label: 'Unarmoured' }]} /></Field>
              <Field label="Insulation"><Choice value={i.insulation} onChange={(v) => set({ insulation: v })} options={[{ value: 'xlpe', label: 'XLPE', hint: '90 °C' }, { value: 'pvc', label: 'PVC', hint: '70 °C · approximate' }]} /></Field>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="form-section">
            <h3>Installation conditions</h3>
            <Choice value={i.installation} onChange={(v) => set({ installation: v })} options={[
              { value: 'buried', label: 'Direct buried', hint: 'Reference 20 °C ground' },
              { value: 'duct', label: 'In duct', hint: 'Buried ducts' },
              { value: 'air', label: 'In air', hint: 'Reference 30 °C air' },
            ]} />
            <div className="form-grid mt-16">
              <Field label="Arrangement" hint={arrs.length === 1 ? 'Only rated arrangement for this construction' : 'Affects the base rating column'}>
                <select value={i.arrangement || ''} onChange={(e) => set({ arrangement: e.target.value })}>{arrs.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}</select>
              </Field>
              {i.installation === 'air' ? (
                <Field label="Ambient air temperature" unit="°C" error={E('air_temp')}><NumInput {...f('air_temp')} /></Field>
              ) : (
                <>
                  <Field label="Soil temperature" unit="°C" error={E('soil_temp')}><NumInput {...f('soil_temp')} /></Field>
                  {i.installation === 'buried' ? (
                    <Field label="Soil thermal resistivity" unit="K·m/W" error={E('soil_resistivity')} hint="Table range 0.7–3.0 (nearest value used)"><NumInput {...f('soil_resistivity')} min={0.1} /></Field>
                  ) : (
                    <Field label="Duct thermal resistivity" unit="K·m/W" error={E('duct_resistivity')} hint="Table range 0.7–3.0 (nearest value used)"><NumInput {...f('duct_resistivity')} min={0.1} /></Field>
                  )}
                  <Field label="Burial depth" unit="m" error={E('depth')} hint="To cable / duct centre; table 0.5–3.0 m"><NumInput {...f('depth')} min={0.1} max={3} /></Field>
                </>
              )}
              <Field label="Cable route length" unit="m" error={E('cable_length')}><NumInput {...f('cable_length')} min={0.1} /></Field>
            </div>
            <p className="small muted mt-8">Parallel runs are evaluated automatically at touching, 200, 400, 600 and 800 mm group spacing (grouping factor applied).</p>
          </div>
        )}

        {step === 3 && (
          <div className="form-section">
            <h3>Short-circuit withstand</h3>
            <p>Adiabatic check I = k·S/√t (IEC 60364-5-54) against the prospective fault current at this point.</p>
            <Toggle checked={i.sc_check} onChange={(v) => set({ sc_check: v })} label="Check short-circuit adequacy" />
            {i.sc_check && (
              <>
                <div className="form-grid mt-16">
                  <Field label="Prospective fault current" unit="kA" error={E('fault_kA')}><NumInput {...f('fault_kA')} min={0.01} /></Field>
                  <Field label="Protection clearing time" unit="s" error={E('fault_time')}><NumInput {...f('fault_time')} min={0.01} max={5} /></Field>
                </div>
                <div className="mt-16">
                  <Field label="Fault sharing between parallel runs">
                    <Choice value={i.fault_share} onChange={(v) => set({ fault_share: v })} options={[
                      { value: 'equal', label: 'Equal sharing', hint: 'Each cable sees fault ÷ runs — assumes an ideal split' },
                      { value: 'full', label: 'Full fault per cable', hint: 'Each cable must withstand the whole fault — conservative' },
                    ]} />
                  </Field>
                </div>
              </>
            )}
          </div>
        )}

        {step === 4 && (
          <div className="form-section">
            <h3>Review inputs</h3>
            <div className="split">
              <KV rows={[
                ['System', `${i.phase === 'three' ? 'Three' : 'Single'}-phase, ${i.voltage} V`],
                ['Load', i.load_mode === 'current' ? `${i.current} A` : `${i.power} ${i.power_unit} at pf ${i.power_factor}`],
                ['Voltage-drop limit', `${i.voltage_drop_limit_pct} %`],
                ['Construction', `${i.material === 'cu' ? 'Copper' : 'Aluminium'}, ${i.core_type === '1C' ? 'single-core' : '3-core'}, ${i.armored ? 'armoured' : 'unarmoured'}, ${i.insulation.toUpperCase()}`],
              ]} />
              <KV rows={[
                ['Installation', `${{ buried: 'Direct buried', duct: 'Duct', air: 'Air' }[i.installation]} — ${arrLabel || '…'}`],
                i.installation === 'air' ? ['Ambient', `${i.air_temp} °C`] : ['Ground', `${i.soil_temp} °C, ρ ${i.installation === 'buried' ? i.soil_resistivity : i.duct_resistivity} K·m/W, depth ${i.depth} m`],
                ['Route length', `${i.cable_length} m`],
                ['Short circuit', i.sc_check ? `${i.fault_kA} kA for ${i.fault_time} s, ${i.fault_share === 'equal' ? 'equal sharing' : 'full fault per cable'}` : 'not checked'],
              ]} />
            </div>
            {allErrors.length > 0 && <div className="error mt-16">Fix before calculating: {allErrors.join('; ')}</div>}
          </div>
        )}

        <div className="toolbar mt-16">
          {step > 0 && <button className="btn-outline" onClick={() => go(step - 1)}>Back</button>}
          <span className="spacer" />
          {step < 4 && <button className="btn-primary" onClick={next} disabled={errCount > 0}>Continue</button>}
          {step === 4 && (
            <button className="btn-primary" onClick={calculate} disabled={c.busy || allErrors.length > 0}>
              {c.busy ? <Spinner light /> : Icon.play} Calculate
            </button>
          )}
        </div>
      </Panel>

      <ErrorBox error={c.error} />
      {c.run && (
        <div id="results" className="mt-16">
          <h2 className="section-title">Results</h2>
          <RunInfo run={c.run} outdated={c.outdated} onRecalc={calculate} busy={c.busy} />
          <SingleFeederResult inputs={c.payload} result={c.run.result} />
          <div className="mt-16"><VerificationNotice /></div>
          <div className="sticky-actions">
            <OutputBar mode="single_feeder" inputs={c.payload} run={c.run} outdated={c.outdated} saved={c.saved} onSaved={c.setSaved} />
          </div>
          <p className="small muted">Compare this with other saved options on the <Link className="table-link" to="/comparison">Comparison</Link> page.</p>
        </div>
      )}
    </div>
  )
}
