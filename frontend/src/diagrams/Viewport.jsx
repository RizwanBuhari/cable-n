// Zoom / pan / reset / export wrapper for engineering diagrams.
// Children are drawn in world coordinates (the given viewBox). `children`
// may be a function receiving { toWorld } so editors can convert pointer
// positions into world coordinates.
import { useCallback, useEffect, useRef, useState } from 'react'
import { saveBlob } from '../lib/api'
import { Icon } from '../components/icons'

export default function Viewport({ box, height = 420, children, tools, caption, fileName = 'cable-n-diagram', title }) {
  const svgRef = useRef(null)
  const [vb, setVb] = useState(box)
  const drag = useRef(null)
  const key = box.join(',')
  useEffect(() => setVb(box), [key]) // eslint-disable-line react-hooks/exhaustive-deps

  const toWorld = useCallback((clientX, clientY) => {
    const svg = svgRef.current
    const pt = svg.createSVGPoint()
    pt.x = clientX
    pt.y = clientY
    const p = pt.matrixTransform(svg.getScreenCTM().inverse())
    return { x: p.x, y: p.y }
  }, [])

  const zoom = (f, cx, cy) => setVb(([x, y, w, h]) => {
    const nw = Math.min(Math.max(w * f, box[2] / 40), box[2] * 8)
    const nh = (h * nw) / w
    const px = cx ?? x + w / 2
    const py = cy ?? y + h / 2
    return [px - ((px - x) * nw) / w, py - ((py - y) * nh) / h, nw, nh]
  })

  useEffect(() => {
    const svg = svgRef.current
    const onWheel = (e) => {
      if (!e.ctrlKey && !e.metaKey && !e.altKey) return // plain wheel scrolls the page
      e.preventDefault()
      const p = toWorld(e.clientX, e.clientY)
      zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15, p.x, p.y)
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }) // eslint-disable-line react-hooks/exhaustive-deps

  function onDown(e) {
    if (e.button !== 0 || e.target.closest('[data-interactive]')) return
    drag.current = { sx: e.clientX, sy: e.clientY, vb }
    svgRef.current.setPointerCapture(e.pointerId)
    svgRef.current.classList.add('panning')
  }
  function onMove(e) {
    if (!drag.current) return
    const r = svgRef.current.getBoundingClientRect()
    const [x, y, w, h] = drag.current.vb
    const s = Math.max(w / r.width, h / r.height)
    setVb([x - (e.clientX - drag.current.sx) * s, y - (e.clientY - drag.current.sy) * s, w, h])
  }
  function onUp() {
    drag.current = null
    svgRef.current?.classList.remove('panning')
  }

  function serialized() {
    const clone = svgRef.current.cloneNode(true)
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    clone.setAttribute('viewBox', box.join(' '))
    clone.setAttribute('width', 1600)
    clone.setAttribute('height', Math.round((1600 * box[3]) / box[2]))
    clone.removeAttribute('class')
    clone.insertAdjacentHTML('afterbegin', '<style>text{font-family:Montserrat,Arial,sans-serif}</style>')
    return { text: new XMLSerializer().serializeToString(clone), w: 1600, h: Math.round((1600 * box[3]) / box[2]) }
  }
  function exportSvg() {
    saveBlob(new Blob([serialized().text], { type: 'image/svg+xml' }), `${fileName}.svg`)
  }
  function exportPng() {
    const { text, w, h } = serialized()
    const img = new Image()
    img.onload = () => {
      const c = document.createElement('canvas')
      c.width = w
      c.height = h
      const ctx = c.getContext('2d')
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, w, h)
      ctx.drawImage(img, 0, 0, w, h)
      c.toBlob((b) => saveBlob(b, `${fileName}.png`), 'image/png')
    }
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text)
  }

  return (
    <div className="diagram">
      <div className="diagram-tools">
        {tools}
        <button onClick={() => zoom(1 / 1.25)} title="Zoom in" aria-label="Zoom in">{Icon.zoomIn}</button>
        <button onClick={() => zoom(1.25)} title="Zoom out" aria-label="Zoom out">{Icon.zoomOut}</button>
        <button onClick={() => setVb(box)} title="Reset view">{Icon.refresh}</button>
        <button onClick={exportSvg} title="Download SVG">SVG</button>
        <button onClick={exportPng} title="Download PNG">PNG</button>
      </div>
      <svg ref={svgRef} className="dg" viewBox={vb.join(' ')} style={{ height }} role="img" aria-label={title || 'Engineering diagram'}
        preserveAspectRatio="xMidYMid meet" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp}>
        {typeof children === 'function' ? children({ toWorld }) : children}
      </svg>
      {caption && <div className="diagram-caption">{caption}<span>Drag to pan · Ctrl + wheel to zoom</span></div>}
    </div>
  )
}

export function DimH({ x1, x2, y, label, color = '#2563eb', size }) {
  const fs = size || Math.max((x2 - x1) * 0.06, 1)
  return (
    <g stroke={color} fill={color} strokeWidth={fs * 0.08}>
      <line x1={x1} y1={y} x2={x2} y2={y} />
      <line x1={x1} y1={y - fs * 0.5} x2={x1} y2={y + fs * 0.5} />
      <line x1={x2} y1={y - fs * 0.5} x2={x2} y2={y + fs * 0.5} />
      <text x={(x1 + x2) / 2} y={y - fs * 0.45} fontSize={fs} textAnchor="middle" stroke="none">{label}</text>
    </g>
  )
}

export function DimV({ x, y1, y2, label, color = '#2563eb', size }) {
  const fs = size || Math.max((y2 - y1) * 0.06, 1)
  return (
    <g stroke={color} fill={color} strokeWidth={fs * 0.08}>
      <line x1={x} y1={y1} x2={x} y2={y2} strokeDasharray={`${fs * 0.4} ${fs * 0.3}`} />
      <line x1={x - fs * 0.5} y1={y1} x2={x + fs * 0.5} y2={y1} />
      <line x1={x - fs * 0.5} y1={y2} x2={x + fs * 0.5} y2={y2} />
      <text x={x + fs * 0.6} y={(y1 + y2) / 2} fontSize={fs} stroke="none" dominantBaseline="middle">{label}</text>
    </g>
  )
}
