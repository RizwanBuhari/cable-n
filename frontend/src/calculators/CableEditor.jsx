// Mode 4 cable definition - the same questions as the original define_cable(),
// grouped into sections, with a live engine preview of what it derives.
import { useEffect, useState } from 'react'
import { Collapsible, ErrorBox, Field, KV, NumInput, Toggle } from '../components/ui'
import { CableSection } from '../diagrams/Diagrams'
import { api } from '../lib/api'
import { num } from '../lib/format'

export const blankCable = () => ({
  desig: '1x630', mat: 'CU', U: 33, f: null, theta: 90, dc: 30.05, tcs: 1.0, ti: 8.0, tis: 0.9, rho_ins: 3.5,
  t_wb: 0, rho_wb: 12, conductor: 'stranded', theta_scr: 85,
  has_wire: false, cu_wire: { dw: 1.0, N: 50 }, has_tape: true, cu_tape: { tt: 0.1, wt: 30, double: false }, has_lead: false, lead: { tl: 2.0 },
  n3_construction: 'screened', D_laidup: null, rho_filler: 5.0, t2: 1.0, G_T2: null, lay_length: 0,
  t_bed: 1.0, rho_bed: 3.5, has_armour: true, armour: { type: 'AWA', da: 2.5, Na: 60, th: 0.5, double: false, R20: null },
  tj: 3.0, rho_j: 3.5, De: null, insulation: 'XLPE', eps: 2.5, tan_delta: 0.001, bonding: 'both_ends',
})

/** Editor state -> the dict build_cable() expects (only what applies). */
export function cablePayload(c) {
  const p = { desig: c.desig, mat: c.mat, U: c.U, f: c.f, theta: c.theta, dc: c.dc, tcs: c.tcs, ti: c.ti, tis: c.tis, rho_ins: c.rho_ins,
    t_wb: c.t_wb, conductor: c.conductor, theta_scr: c.theta_scr, t_bed: c.t_bed, rho_bed: c.rho_bed, tj: c.tj, rho_j: c.rho_j, De: c.De,
    insulation: c.insulation, bonding: c.bonding }
  if (c.t_wb > 0) p.rho_wb = c.rho_wb
  if (c.has_wire) p.cu_wire = { dw: c.cu_wire.dw, N: c.cu_wire.N }
  if (c.has_tape) p.cu_tape = { tt: c.cu_tape.tt, wt: c.cu_tape.wt, double: !!c.cu_tape.double }
  if (c.has_lead) p.lead = { tl: c.lead.tl }
  if (String(c.desig).trim().startsWith('3')) {
    Object.assign(p, { n3_construction: c.n3_construction, D_laidup: c.D_laidup })
    if (c.n3_construction !== 'belted') Object.assign(p, { rho_filler: c.rho_filler, t2: c.t2, G_T2: c.G_T2, lay_length: c.lay_length })
  }
  if (c.has_armour) {
    const a = c.armour
    p.armour = ['AWA', 'SWA'].includes(a.type) ? { type: a.type, da: a.da, Na: a.Na, R20: a.R20 } : { type: a.type, th: a.th, double: !!a.double, R20: a.R20 }
  }
  if (!['XLPE', 'EPR', 'PILC', 'PVC'].includes(c.insulation)) Object.assign(p, { eps: c.eps, tan_delta: c.tan_delta })
  Object.keys(p).forEach((k) => (p[k] === null || p[k] === undefined) && delete p[k])
  return p
}

/** A preset / saved payload -> editor state. */
export function cableFromPayload(p) {
  const b = blankCable()
  return { ...b, ...p, has_wire: !!p.cu_wire, cu_wire: p.cu_wire || b.cu_wire, has_tape: !!p.cu_tape, cu_tape: { ...b.cu_tape, ...(p.cu_tape || {}) },
    has_lead: !!p.lead, lead: p.lead || b.lead, has_armour: !!p.armour, armour: { ...b.armour, ...(p.armour || {}) },
    f: p.f ?? null, De: p.De ?? null, D_laidup: p.D_laidup ?? null, G_T2: p.G_T2 ?? null }
}

export default function CableEditor({ cable: c, onChange, standard }) {
  const [preview, setPreview] = useState(null)
  const [err, setErr] = useState(null)
  const three = String(c.desig).trim().startsWith('3')
  const n = (k, extra = {}) => ({ value: c[k], onChange: (v) => onChange({ ...c, [k]: v }), ...extra })
  const sub = (o, k) => ({ value: c[o][k], onChange: (v) => onChange({ ...c, [o]: { ...c[o], [k]: v } }) })
  const payloadKey = JSON.stringify(cablePayload(c))
  useEffect(() => {
    const t = setTimeout(() => {
      api('/calculations/advanced-mvhv/cable-preview', { method: 'POST', body: { cable: cablePayload(c), standard } })
        .then((r) => { setPreview(r); setErr(null) })
        .catch((e) => { setPreview(null); setErr(e) })
    }, 450)
    return () => clearTimeout(t)
  }, [payloadKey, standard]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="split">
      <div>
        <Collapsible title="Identification & ratings" defaultOpen>
          <div className="form-grid">
            <Field label="Designation" hint="1x<size> or 3x<size>"><input value={c.desig} onChange={(e) => onChange({ ...c, desig: e.target.value })} /></Field>
            <Field label="Conductor"><select value={c.mat} onChange={(e) => onChange({ ...c, mat: e.target.value })}><option value="CU">Copper</option><option value="AL">Aluminium</option></select></Field>
            <Field label="Rated voltage U (phase-phase)" unit="kV"><NumInput {...n('U')} /></Field>
            <Field label="Frequency" unit="Hz" hint="Blank = standard default"><NumInput {...n('f')} /></Field>
            <Field label="Max conductor temperature" unit="°C"><NumInput {...n('theta')} /></Field>
            <Field label="Insulation" tip="Sets ε and tan δ for the dielectric loss Wd (IEC 60287-1-1 Table 1).">
              <select value={c.insulation} onChange={(e) => onChange({ ...c, insulation: e.target.value })}><option>XLPE</option><option>EPR</option><option>PILC</option><option>PVC</option><option value="CUSTOM">Enter ε / tan δ</option></select>
            </Field>
            {c.insulation === 'CUSTOM' && <><Field label="Relative permittivity ε"><NumInput {...n('eps')} /></Field><Field label="tan δ"><NumInput {...n('tan_delta')} /></Field></>}
            <Field label="Bonding" tip="Both-ends bonding causes circulating currents in screen and armour (λ1, λ2).">
              <select value={c.bonding} onChange={(e) => onChange({ ...c, bonding: e.target.value })}><option value="both_ends">Both ends / solid</option><option value="single">Single-point / cross-bonded</option></select>
            </Field>
          </div>
        </Collapsible>
        <Collapsible title="Conductor & insulation (per core)" defaultOpen>
          <div className="form-grid">
            <Field label="Conductor diameter dc" unit="mm"><NumInput {...n('dc')} /></Field>
            <Field label="Conductor construction" tip="IEC 60287-1-1 Table 2 skin/proximity coefficients ks, kp.">
              <select value={c.conductor} onChange={(e) => onChange({ ...c, conductor: e.target.value })}><option value="stranded">Round stranded / compacted</option><option value="solid">Round solid</option><option value="milliken">Milliken / segmental</option></select>
            </Field>
            <Field label="Conductor screen" unit="mm"><NumInput {...n('tcs')} /></Field>
            <Field label="Insulation thickness" unit="mm"><NumInput {...n('ti')} /></Field>
            <Field label="Insulation screen" unit="mm"><NumInput {...n('tis')} /></Field>
            <Field label="Insulation ρ" unit="K·m/W"><NumInput {...n('rho_ins')} /></Field>
            <Field label="Water-blocking tape on conductor" unit="mm" hint="0 = none; thickness included in the conductor screen"><NumInput {...n('t_wb')} /></Field>
            {c.t_wb > 0 && <Field label="Tape ρ" unit="K·m/W"><NumInput {...n('rho_wb')} /></Field>}
          </div>
        </Collapsible>
        <Collapsible title="Metallic screen / sheath">
          <Field label="Screen operating temperature" unit="°C"><NumInput {...n('theta_scr')} /></Field>
          <div className="mt-8"><Toggle checked={c.has_wire} onChange={(v) => onChange({ ...c, has_wire: v })} label="Copper wire screen" /></div>
          {c.has_wire && <div className="form-grid mt-8"><Field label="Wire diameter" unit="mm"><NumInput {...sub('cu_wire', 'dw')} /></Field><Field label="Number of wires"><NumInput {...sub('cu_wire', 'N')} step={1} /></Field></div>}
          <div className="mt-8"><Toggle checked={c.has_tape} onChange={(v) => onChange({ ...c, has_tape: v })} label="Copper tape screen" /></div>
          {c.has_tape && (
            <div className="form-grid mt-8">
              <Field label="Tape thickness" unit="mm"><NumInput {...sub('cu_tape', 'tt')} /></Field>
              <Field label="Tape width" unit="mm"><NumInput {...sub('cu_tape', 'wt')} /></Field>
              <label className="inline-check"><input type="checkbox" checked={!!c.cu_tape.double} onChange={(e) => onChange({ ...c, cu_tape: { ...c.cu_tape, double: e.target.checked } })} /> Double tape</label>
            </div>
          )}
          <div className="mt-8"><Toggle checked={c.has_lead} onChange={(v) => onChange({ ...c, has_lead: v })} label="Lead sheath" /></div>
          {c.has_lead && <div className="form-grid mt-8"><Field label="Lead thickness" unit="mm"><NumInput {...sub('lead', 'tl')} /></Field></div>}
        </Collapsible>
        {three && (
          <Collapsible title="Three-core lay-up" defaultOpen>
            <div className="form-grid">
              <Field label="Construction"><select value={c.n3_construction} onChange={(e) => onChange({ ...c, n3_construction: e.target.value })}><option value="screened">Screened / SL-type</option><option value="belted">Belted</option></select></Field>
              <Field label="Measured laid-up diameter" unit="mm" hint="Blank = 2.155 × core diameter"><NumInput {...n('D_laidup')} /></Field>
              {c.n3_construction !== 'belted' && (
                <>
                  <Field label="Filler ρ" unit="K·m/W"><NumInput {...n('rho_filler')} /></Field>
                  <Field label="Thickness between core screens and armour" unit="mm"><NumInput {...n('t2')} /></Field>
                  <Field label="Geometric factor G" hint="Blank = IEC 60287-2-1 Fig. 6 fit" tip="T2 = ρ·G/(6π). The fit is validated for t/d 0.045–0.06."><NumInput {...n('G_T2')} /></Field>
                  <Field label="Core lay length" unit="mm" hint="0 = ignore lay-up (C, Ich, Wd ~10–15 % low)"><NumInput {...n('lay_length')} /></Field>
                </>
              )}
            </div>
          </Collapsible>
        )}
        <Collapsible title="Bedding, armour & jacket">
          <div className="form-grid">
            <Field label="Bedding / inner sheath" unit="mm"><NumInput {...n('t_bed')} /></Field>
            <Field label="Bedding ρ" unit="K·m/W"><NumInput {...n('rho_bed')} /></Field>
          </div>
          <div className="mt-8"><Toggle checked={c.has_armour} onChange={(v) => onChange({ ...c, has_armour: v })} label="Armoured" /></div>
          {c.has_armour && (
            <div className="form-grid mt-8">
              <Field label="Armour type"><select value={c.armour.type} onChange={(e) => onChange({ ...c, armour: { ...c.armour, type: e.target.value } })}><option value="AWA">AWA — aluminium wire</option><option value="SWA">SWA — steel wire</option><option value="STA">STA — steel tape</option><option value="ATA">ATA — aluminium tape</option></select></Field>
              {['AWA', 'SWA'].includes(c.armour.type) ? (
                <><Field label="Wire diameter" unit="mm"><NumInput {...sub('armour', 'da')} /></Field><Field label="Number of wires"><NumInput {...sub('armour', 'Na')} step={1} /></Field></>
              ) : (
                <><Field label="Tape thickness" unit="mm"><NumInput {...sub('armour', 'th')} /></Field><label className="inline-check"><input type="checkbox" checked={!!c.armour.double} onChange={(e) => onChange({ ...c, armour: { ...c.armour, double: e.target.checked } })} /> Double tape</label></>
              )}
              <Field label="Armour DC resistance at 20 °C" unit="Ω/km" hint="Blank = from area (steel wire runs higher in reality)"><NumInput {...sub('armour', 'R20')} /></Field>
            </div>
          )}
          <div className="form-grid mt-8">
            <Field label="Outer jacket" unit="mm"><NumInput {...n('tj')} /></Field>
            <Field label="Jacket ρ" unit="K·m/W"><NumInput {...n('rho_j')} /></Field>
            <Field label="Overall diameter De" unit="mm" hint={preview ? `Blank = build-up ${num(preview.info?.De_computed, 2)} mm` : 'Blank = computed build-up'}><NumInput {...n('De')} /></Field>
          </div>
        </Collapsible>
      </div>
      <div>
        <ErrorBox error={err} />
        {preview && (
          <>
            <CableSection cable={preview} height={280} />
            <div className="mt-8">
              <KV rows={[
                ['U0', `${num(preview.U0, 2)} kV`],
                ['Diameters Dcs / Di / Dis', `${num(preview.Dcs, 2)} / ${num(preview.Di, 2)} / ${num(preview.Dis, 2)} mm`],
                ['Over screen / overall De', `${num(preview.D_over_screen, 2)} / ${num(preview.De, 2)} mm`],
                ['T1 / T2 / T3', `${num(preview.T1, 4)} / ${num(preview.T2, 4)} / ${num(preview.T3, 4)} K·m/W`, 'Thermal resistances: insulation, bedding/filler, outer covering (IEC 60287-2-1).'],
                ['Dielectric loss Wd', `${num(preview.info?.Wd_preview, 4)} W/m per phase`],
                ['Screen resistance (hot)', preview.Rs_hot > 1e6 ? 'no metallic screen' : `${num(preview.Rs_hot, 4)} Ω/km`],
                preview.info?.G_fig6 !== undefined && ['Fig. 6 G (t/d)', `${num(preview.info.G_fig6, 5)} (${num(preview.info.t_over_d, 4)})`],
                preview.C_LL && preview.C_LL !== 1 && ['Core lay factor C_LL', num(preview.C_LL, 5)],
              ]} />
              {preview.info?.warning_no_screen && <p className="small" style={{ color: 'var(--warn)' }}>{preview.info.warning_no_screen}</p>}
              {preview.info?.warning_De && <p className="small" style={{ color: 'var(--warn)' }}>{preview.info.warning_De}</p>}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
