// Display formatting. Values are only rounded for DISPLAY - stored and exported
// results keep the engine's full precision.
export function num(v, d = 2) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })
}
export const int = (v) => num(v, 0)
export const pct = (v, d = 1) => (v === null || v === undefined ? '—' : `${num(v, d)} %`)

export function dateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}
export function timeAgo(iso) {
  if (!iso) return '—'
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const h = Math.floor(mins / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
export function bytes(n) {
  if (!n && n !== 0) return '—'
  const u = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i += 1 }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`
}

export const MODE_LABEL = {
  single_feeder: 'Single feeder sizing',
  batch: 'Batch cable schedule',
  current_rating: 'Current-rating verification',
  advanced_mvhv: 'Advanced MV/HV analysis',
}
export const MODE_PATH = {
  single_feeder: '/calculators/single-feeder',
  batch: '/calculators/batch',
  current_rating: '/calculators/current-rating',
  advanced_mvhv: '/calculators/advanced-mv-hv',
}

/** Stable stringify for "are inputs still the ones that produced this result?". */
export function stableKey(obj) {
  const seen = (v) => (v && typeof v === 'object' && !Array.isArray(v)
    ? Object.keys(v).sort().reduce((a, k) => ((a[k] = seen(v[k])), a), {})
    : Array.isArray(v) ? v.map(seen) : v)
  return JSON.stringify(seen(obj))
}
