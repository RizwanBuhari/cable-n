// Engineering diagrams. Each states whether it is a schematic or to scale,
// and only draws what the inputs / engine results actually contain.
import { useMemo, useState } from 'react'
import { num } from '../lib/format'
import Viewport, { DimH, DimV } from './Viewport'

const SOIL = '#e6d3b3'
const SOIL_LINE = '#9a7b4f'
const CU = '#c77c3c'
const AL = '#a9b0b8'
const INS = '#f4f5f6'
const SCREEN = '#3b3b3b'
const DUCT = '#8a8f96'

function Hatch({ x1, x2, y, s }) {
  const n = Math.max(6, Math.round((x2 - x1) / (s * 1.2)))
  const st = (x2 - x1) / n
  return (
    <g stroke={SOIL_LINE} strokeWidth={s * 0.08}>
      <line x1={x1} y1={y} x2={x2} y2={y} strokeWidth={s * 0.14} />
      {Array.from({ length: n }, (_, i) => <line key={i} x1={x1 + i * st} y1={y} x2={x1 + i * st + s * 0.6} y2={y - s * 0.6} />)}
    </g>
  )
}

// ---------------------------------------------------------------- Mode 1 schematic
function Group({ cx, cy, r, core, formation, duct, material }) {
  const cond = material === 'al' ? AL : CU
  const cable = (x, y, k) => (
    <g key={k}>
      <circle cx={x} cy={y} r={r} fill="#2b2b2b" />
      <circle cx={x} cy={y} r={r * 0.78} fill={INS} />
      <circle cx={x} cy={y} r={r * 0.42} fill={cond} />
    </g>
  )
  const three = (x, y, k) => (
    <g key={k}>
      <circle cx={x} cy={y} r={r * 1.45} fill="#2b2b2b" />
      {[-90, 30, 150].map((d, i) => {
        const a = (d * Math.PI) / 180
        const px = x + r * 0.68 * Math.cos(a)
        const py = y + r * 0.68 * Math.sin(a)
        return <g key={i}><circle cx={px} cy={py} r={r * 0.62} fill={INS} /><circle cx={px} cy={py} r={r * 0.32} fill={cond} /></g>
      })}
    </g>
  )
  if (core === '3C') {
    return <g>{duct && <circle cx={cx} cy={cy} r={r * 2.1} fill="none" stroke={DUCT} strokeWidth={r * 0.18} />}{three(cx, cy, 0)}</g>
  }
  let pts
  if (formation === 'flat') pts = [[cx - 2 * r, cy], [cx, cy], [cx + 2 * r, cy]]
  else pts = [[cx, cy - r * 0.58], [cx - r, cy + r * 0.58], [cx + r, cy + r * 0.58]]
  return (
    <g>
      {duct && formation !== 'flat' && <circle cx={cx} cy={cy} r={r * 2.35} fill="none" stroke={DUCT} strokeWidth={r * 0.18} />}
      {duct && formation === 'flat' && pts.map(([x, y], i) => <circle key={`d${i}`} cx={x} cy={y} r={r * 1.35} fill="none" stroke={DUCT} strokeWidth={r * 0.16} />)}
      {pts.map(([x, y], i) => cable(x, y, i))}
    </g>
  )
}

/** Schematic of a Mode 1 / Mode 2 solution: groups not to scale, values as entered. */
export function FeederDiagram({ installation, arrangement, coreType, runs = 1, spacing = 'Touching', depth, material, label }) {
  const flat = /flat/i.test(arrangement || '')
  const duct = installation === 'duct' || /^Duct/.test(arrangement || '')
  const formation = flat ? 'flat' : 'trefoil'
  const r = 10
  const gw = coreType === '3C' ? r * 3 : flat ? r * 6 : r * 4
  const ductPad = duct ? r * 1.6 : 0
  const gap = spacing === 'Touching' || spacing === 'N/A' ? 0 : 40
  const pitch = gw + ductPad + gap
  const n = Math.max(1, runs)
  const totalW = pitch * (n - 1) + gw + ductPad
  const buried = installation !== 'air'
  const W = Math.max(totalW + 160, 360)
  const groundY = 40
  const cy = buried ? 170 : 120
  const x0 = (W - totalW) / 2 + (gw + ductPad) / 2
  const centers = Array.from({ length: n }, (_, i) => x0 + i * pitch)
  const H = buried ? 250 : 200
  return (
    <Viewport box={[0, 0, W, H]} height={300} fileName="cable-n-feeder-schematic" title="Installation schematic"
      caption={<span><b>Schematic</b> — not to scale. {label}</span>}>
      <rect x="0" y="0" width={W} height={H} fill="#fff" />
      {buried && <rect x="0" y={groundY} width={W} height={H - groundY} fill={SOIL} />}
      {buried && <Hatch x1={0} x2={W} y={groundY} s={10} />}
      {!buried && <text x={12} y={22} fontSize="11" fill="#6f7378">Free air (ambient)</text>}
      {centers.map((x, i) => (
        <g key={i}>
          <Group cx={x} cy={cy} r={r} core={coreType} formation={formation} duct={duct} material={material} />
          {n > 1 && <text x={x} y={cy + r * 4.2} fontSize="10" textAnchor="middle" fill="#333">Run {i + 1}</text>}
        </g>
      ))}
      {buried && depth && <DimV x={centers[0] - (gw + ductPad) / 2 - 22} y1={groundY} y2={cy} label={`${num(depth, 2)} m`} size={10} />}
      {n > 1 && gap > 0 && (
        <DimH x1={centers[0] + (gw + ductPad) / 2} x2={centers[1] - (gw + ductPad) / 2} y={cy - r * 3.6} label={`${spacing} mm`} size={10} />
      )}
      {n > 1 && gap === 0 && <text x={W / 2} y={cy - r * 3.6} fontSize="10" textAnchor="middle" fill="#2563eb">groups touching</text>}
    </Viewport>
  )
}

// ---------------------------------------------------------------- Mode 3 bank layout (to scale)
const utilColor = (u, status) => {
  if (status === 'OVERLOAD') return '#a8121e'
  if (u === null || u === undefined) return '#6f7378'
  if (u > 85) return '#b45309'
  return '#1e7a34'
}

export function BankDiagram({ banks, gaps = [], positions = [], installation, selected, onSelect, showDims = true }) {
  // geometry in mm; x across, y depth down from grade
  const layout = useMemo(() => {
    let cursor = 0
    return banks.map((b, i) => {
      const x0 = i === 0 ? 0 : cursor + (gaps[i - 1] || 0.5) * 1000
      const w = (b.cols - 1) * b.h_pitch
      cursor = x0 + w
      return { ...b, x0, w, top: b.top_depth * 1000, h: (b.rows - 1) * (b.v_pitch || 0) }
    })
  }, [banks, gaps])
  if (!layout.length) return null
  const pitchMin = Math.min(...layout.map((b) => Math.min(b.h_pitch, b.rows > 1 ? b.v_pitch || b.h_pitch : b.h_pitch)))
  const rD = pitchMin * 0.36
  const minX = -pitchMin * 1.6
  const maxX = layout[layout.length - 1].x0 + layout[layout.length - 1].w + pitchMin * 1.6
  const maxY = Math.max(...layout.map((b) => b.top + b.h)) + pitchMin * 1.6
  const W = maxX - minX
  const fs = Math.max(W / 55, pitchMin * 0.22)
  const posMap = Object.fromEntries(positions.map((p) => [`${p.bank}-${p.row}-${p.col}`, p]))
  return (
    <Viewport box={[minX, -fs * 3, W, maxY + fs * 3]} fileName="cable-n-bank-layout" title="Bank layout"
      caption={<span><b>To scale</b> (positions from entered pitches, depths and gaps). Colour: green ≤ 85 % utilised, amber &gt; 85 %, red overload, grey no load entered.</span>}>
      <rect x={minX} y={0} width={W} height={maxY} fill={SOIL} />
      <Hatch x1={minX} x2={maxX} y={0} s={fs} />
      {layout.map((b, bi) => (
        <g key={bi}>
          {installation === 'duct' && (
            <rect x={b.x0 - b.h_pitch * 0.55} y={b.top - (b.v_pitch || b.h_pitch) * 0.55} width={b.w + b.h_pitch * 1.1}
              height={b.h + (b.v_pitch || b.h_pitch) * 1.1} fill="#d7d9dc" stroke="#9ca0a6" strokeWidth={fs * 0.08} rx={fs * 0.3} />
          )}
          <text x={b.x0 + b.w / 2} y={b.top - (b.v_pitch || b.h_pitch) * 0.55 - fs * 0.5} fontSize={fs} textAnchor="middle" fill="#212121" fontWeight="700">Bank {bi + 1}</text>
          {Array.from({ length: b.rows }, (_, r) => Array.from({ length: b.cols }, (_, c) => {
            const x = b.x0 + c * b.h_pitch
            const y = b.top + r * (b.v_pitch || 0)
            const p = posMap[`${bi + 1}-${r + 1}-${c + 1}`]
            const sel = selected && selected.bank === bi + 1 && selected.row === r + 1 && selected.col === c + 1
            return (
              <g key={`${r}-${c}`} data-interactive className={onSelect ? 'clickable' : ''} onClick={() => onSelect?.({ bank: bi + 1, row: r + 1, col: c + 1 })}>
                <circle cx={x} cy={y} r={rD} fill={p ? '#fff' : 'rgba(255,255,255,.35)'} stroke={sel ? '#2563eb' : DUCT}
                  strokeWidth={sel ? fs * 0.25 : fs * 0.1} strokeDasharray={p ? undefined : `${fs * 0.3} ${fs * 0.25}`} />
                {p && (
                  <>
                    <circle cx={x} cy={y} r={rD * 0.62} fill={utilColor(p.util, p.status)} />
                    <text x={x} y={y + fs * 0.35} fontSize={fs * 0.85} textAnchor="middle" fill="#fff" fontWeight="700">{p.desig}</text>
                    {p.iz !== undefined && <text x={x} y={y + rD + fs * 1.1} fontSize={fs * 0.8} textAnchor="middle" fill="#212121">{num(p.iz, 0)} A</text>}
                  </>
                )}
              </g>
            )
          }))}
          {showDims && b.cols > 1 && <DimH x1={b.x0} x2={b.x0 + b.h_pitch} y={b.top + b.h + rD + fs * 2.6} label={`${b.h_pitch} mm`} size={fs * 0.85} />}
          {showDims && b.rows > 1 && <DimV x={b.x0 + b.w + rD + fs * 1.2} y1={b.top} y2={b.top + b.v_pitch} label={`${b.v_pitch} mm`} size={fs * 0.85} />}
          {showDims && bi === 0 && <DimV x={b.x0 - rD - fs * 1.6} y1={0} y2={b.top} label={`${b.top_depth} m`} size={fs * 0.85} />}
          {showDims && bi > 0 && (
            <DimH x1={layout[bi - 1].x0 + layout[bi - 1].w} x2={b.x0} y={b.top - (b.v_pitch || b.h_pitch) * 0.9 - fs} label={`${gaps[bi - 1]} m`} size={fs * 0.85} />
          )}
        </g>
      ))}
    </Viewport>
  )
}

// ---------------------------------------------------------------- Mode 4 arrangement (to scale)
const tempColor = (t, tmax) => {
  if (t === null || t === undefined) return '#6f7378'
  if (t > tmax + 0.05) return '#a8121e'
  if (t >= tmax - 0.5) return '#CE1B28'
  const f = Math.max(0, Math.min(1, (t - 20) / Math.max(tmax - 20, 1)))
  return `hsl(${210 - f * 190}, 70%, ${45 + (1 - f) * 10}%)`
}

export function ArrangementDiagram({ result, selected, onSelect, editable, onMoveCircuit, isotherms }) {
  const [labels, setLabels] = useState(true)
  const [dims, setDims] = useState(true)
  const [iso, setIso] = useState(false)
  const [dragX, setDragX] = useState(null)
  const placed = result.placed
  const air = result.installation === 'air'
  const duct = result.duct
  const Do = duct ? duct[0] : null
  const xs = placed.map((p) => p.x)
  const ys = placed.map((p) => p.y)
  const rMax = Math.max(...placed.map((p) => (Do || p.De) / 2))
  let minX = Math.min(...xs) - rMax * 6 - 300
  let maxX = Math.max(...xs) + rMax * 6 + 300
  if (result.banks) {
    for (const b of result.banks) {
      minX = Math.min(minX, b.x0 - b.hp - 300)
      maxX = Math.max(maxX, b.x0 + (b.cols - 1) * b.hp + b.hp + 300)
    }
  }
  const top = air ? Math.min(...ys) - rMax * 8 - 200 : -Math.max(150, (maxX - minX) * 0.05)
  const bottom = Math.max(...ys) + rMax * 6 + 300
  const W = maxX - minX
  const fs = Math.max(W / 60, 14)
  const circuits = useMemo(() => {
    const m = {}
    placed.forEach((p) => {
      const c = p.tag.split('-')[0]
      ;(m[c] = m[c] || []).push(p)
    })
    return m
  }, [placed])
  const canDrag = editable && result.installation === 'buried'

  return (
    <Viewport box={[minX, top, W, bottom - top]} height={460} fileName="cable-n-arrangement" title="Cable arrangement"
      tools={(
        <>
          <button className={labels ? 'on' : ''} onClick={() => setLabels((v) => !v)}>Labels</button>
          <button className={dims ? 'on' : ''} onClick={() => setDims((v) => !v)}>Dimensions</button>
          {isotherms?.available && <button className={iso ? 'on' : ''} onClick={() => setIso((v) => !v)}>Heat map</button>}
        </>
      )}
      caption={(
        <span>
          <b>To scale</b> — engine coordinates (mm). Colour = conductor temperature at the rating/load.
          {iso && ' Heat map: indicative superposed temperature rise (image method), not a finite-element field.'}
          {canDrag && ' Drag a circuit sideways to move it, then recalculate.'}
        </span>
      )}>
      {({ toWorld }) => (
        <g onPointerMove={(e) => {
          if (!dragX) return
          const w = toWorld(e.clientX, e.clientY)
          setDragX({ ...dragX, x: Math.round((w.x - dragX.offset) / 10) * 10 })
        }} onPointerUp={() => {
          if (dragX) onMoveCircuit?.(dragX.circuit, dragX.x)
          setDragX(null)
        }}>
          <rect x={minX} y={top} width={W} height={bottom - top} fill="#fff" />
          {!air && <rect x={minX} y={0} width={W} height={bottom} fill={SOIL} />}
          {!air && <Hatch x1={minX} x2={maxX} y={0} s={fs} />}
          {!air && (result.backfill_rho || result.trough_flag) && (
            <text x={minX + fs} y={fs * 2.2} fontSize={fs * 0.8} fill="#6f4f22">
              {result.trough_flag ? 'Concrete trough' : 'Special backfill'} ρ {num(result.rho_e, 2)} K·m/W · native ρ {num(result.rho_native, 2)} K·m/W
            </text>
          )}
          {iso && isotherms?.available && (() => {
            const g = isotherms
            const cw = (g.maxx - g.minx) / g.cols
            const ch = (g.maxy - g.miny) / g.rows
            const mx = Math.max(...g.grid.flat())
            return (
              <g opacity="0.55">
                {g.grid.map((row, j) => row.map((v, i) => (
                  <rect key={`${i}-${j}`} x={g.minx + i * cw} y={g.miny + j * ch} width={cw + 1} height={ch + 1}
                    fill={`hsl(${220 - (v / mx) * 220}, 85%, 55%)`} />
                )))}
              </g>
            )
          })()}
          {result.banks?.map((b) => (
            <g key={b.id}>
              <rect x={b.x0 - b.hp / 2} y={b.top - (b.vp || b.hp) / 2} width={(b.cols - 1) * b.hp + b.hp} height={(b.rows - 1) * b.vp + (b.vp || b.hp)}
                fill="#d7d9dc" stroke="#9ca0a6" strokeWidth={fs * 0.08} />
              {labels && <text x={b.x0 + ((b.cols - 1) * b.hp) / 2} y={b.top - (b.vp || b.hp) / 2 - fs * 0.5} fontSize={fs} textAnchor="middle" fontWeight="700">Bank {b.id}</text>}
              {b.coords.map((c) => (
                <circle key={`${c.row}-${c.col}`} cx={c.x} cy={c.y} r={Do / 2} fill="rgba(255,255,255,.6)" stroke={DUCT} strokeWidth={fs * 0.07} />
              ))}
            </g>
          ))}
          {Object.entries(circuits).map(([cname, ps]) => {
            const shift = dragX && dragX.circuit === cname ? dragX.x - dragX.x0 : 0
            const cx = ps.reduce((s, p) => s + p.x, 0) / ps.length
            return (
              <g key={cname} data-interactive={canDrag || onSelect ? '' : undefined} transform={`translate(${shift} 0)`}
                style={canDrag ? { cursor: 'ew-resize' } : undefined}
                onPointerDown={(e) => {
                  if (!canDrag) return
                  e.stopPropagation()
                  e.currentTarget.ownerSVGElement.setPointerCapture?.(e.pointerId)
                  const w = toWorld(e.clientX, e.clientY)
                  setDragX({ circuit: cname, x0: cx, x: cx, offset: w.x - cx })
                }}>
                {ps.map((p) => {
                  const sel = selected === p.tag
                  return (
                    <g key={p.tag} className={onSelect ? 'clickable' : ''} onClick={() => onSelect?.(p.tag)}>
                      <circle cx={p.x} cy={p.y} r={p.De / 2} fill={tempColor(p.theta_op, p.theta_max)} stroke={sel ? '#2563eb' : '#212121'}
                        strokeWidth={sel ? Math.max(p.De * 0.08, fs * 0.15) : p.De * 0.03} />
                      {p.n === 3 && [-90, 30, 150].map((d, i) => {
                        const a = (d * Math.PI) / 180
                        return <circle key={i} cx={p.x + p.De * 0.2 * Math.cos(a)} cy={p.y + p.De * 0.2 * Math.sin(a)} r={p.De * 0.17} fill="#fff" opacity="0.75" />
                      })}
                      {labels && <text x={p.x} y={p.y + (Do || p.De) / 2 + fs * 1.05} fontSize={fs * 0.72} textAnchor="middle" fill="#212121">{p.tag} · {num(p.I, 0)} A</text>}
                    </g>
                  )
                })}
                {shift !== 0 && <text x={cx} y={ps[0].y - rMax * 2.5} fontSize={fs} textAnchor="middle" fill="#2563eb" fontWeight="700">x = {num(cx + shift, 0)} mm</text>}
              </g>
            )
          })}
          {dims && !air && (() => {
            const p0 = placed.reduce((a, b) => (a.y < b.y ? a : b))
            return <DimV x={minX + fs * 3} y1={0} y2={p0.y} label={`${num(p0.y, 0)} mm`} size={fs} />
          })()}
          {dims && Object.keys(circuits).length > 1 && (() => {
            const cs = Object.values(circuits).map((ps) => ps.reduce((s, p) => s + p.x, 0) / ps.length).sort((a, b) => a - b)
            const y = Math.min(...ys) - rMax * 3.2
            return <DimH x1={cs[0]} x2={cs[1]} y={y} label={`${num(cs[1] - cs[0], 0)} mm`} size={fs} />
          })()}
        </g>
      )}
    </Viewport>
  )
}

// ---------------------------------------------------------------- cable cross-section (to scale)
export function CableSection({ cable, height = 320 }) {
  if (!cable) return null
  const c = cable
  const R = c.De / 2
  const cond = c.mat === 'AL' ? AL : CU
  const sw = R * 0.006
  const core = (x, y, k) => (
    <g key={k}>
      {c.screen_layers?.length > 0 && <circle cx={x} cy={y} r={(c.n === 3 ? coreOuter : c.D_over_screen) / 2} fill="#b87333" />}
      <circle cx={x} cy={y} r={c.Dis / 2} fill={SCREEN} />
      <circle cx={x} cy={y} r={c.Di / 2} fill={INS} stroke="#c9ccd0" strokeWidth={sw} />
      <circle cx={x} cy={y} r={c.Dcs / 2} fill={SCREEN} />
      <circle cx={x} cy={y} r={c.dc / 2} fill={cond} />
    </g>
  )
  const coreOuter = c.n === 3 ? (c.D_laidup || c.D_over_screen) / (1 + 2 / Math.sqrt(3)) : c.D_over_screen
  const arm = c.armour
  const armDm = arm?.dmean
  return (
    <Viewport box={[-R * 1.25, -R * 1.25, R * 2.5, R * 2.5]} height={height} fileName={`cable-n-section-${c.desig}`} title="Cable cross-section"
      caption={<span><b>To scale</b> from the entered construction — De {num(c.De, 1)} mm.</span>}>
      <circle cx={0} cy={0} r={R} fill="#1f1f1f" />
      <circle cx={0} cy={0} r={R - c.tj} fill="#5a5d61" />
      {arm && arm.kind === 'wires' && (() => {
        const n = Math.max(8, Math.round((Math.PI * armDm) / arm.th))
        return Array.from({ length: n }, (_, i) => {
          const a = (i / n) * Math.PI * 2
          return <circle key={i} cx={(armDm / 2) * Math.cos(a)} cy={(armDm / 2) * Math.sin(a)} r={arm.th / 2 * 0.95} fill={arm.mat === 'steel' ? '#8d949b' : '#c4cad0'} />
        })
      })()}
      {arm && arm.kind === 'tape' && <circle cx={0} cy={0} r={armDm / 2} fill="none" stroke="#8d949b" strokeWidth={arm.th} />}
      <circle cx={0} cy={0} r={(arm ? armDm - arm.th : R * 2 - 2 * c.tj) / 2} fill="#7a7d81" />
      {c.n === 3 ? (
        <>
          <circle cx={0} cy={0} r={(c.D_laidup || c.D_over_screen) / 2} fill="#9fa3a8" />
          {[-90, 30, 150].map((d, i) => {
            const a = (d * Math.PI) / 180
            const rr = coreOuter / Math.sqrt(3)
            return core(rr * Math.cos(a), rr * Math.sin(a), i)
          })}
        </>
      ) : core(0, 0, 0)}
    </Viewport>
  )
}
