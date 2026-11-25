// Thin client for the stateless Cable-N API. No credentials, no cookies.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export const SLUG = {
  single_feeder: 'single-feeder', batch: 'batch', current_rating: 'current-rating', advanced_mvhv: 'advanced-mvhv',
}

export class ApiError extends Error {
  constructor(status, message, errors = []) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

async function parseError(res) {
  let msg = `Request failed (${res.status})`
  let errors = []
  try {
    const j = await res.json()
    const d = j.detail
    if (typeof d === 'string') msg = d
    else if (d && typeof d === 'object') {
      msg = d.message || msg
      errors = d.errors || []
    }
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 429 && !/wait|limit/i.test(msg)) msg = 'Too many requests — please wait a moment.'
  return new ApiError(res.status, msg, errors)
}

export async function api(path, { method = 'GET', body, signal, form } = {}) {
  let res
  try {
    res = await fetch(API_BASE + path, {
      method,
      signal,
      headers: body && !form ? { 'Content-Type': 'application/json' } : undefined,
      body: form || (body ? JSON.stringify(body) : undefined),
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError(0, 'Cannot reach the Cable-N calculation server. Check your connection and try again.')
  }
  if (!res.ok) throw await parseError(res)
  return res.json()
}

export const runCalc = (mode, inputs, signal) => api(`/calculations/${SLUG[mode]}`, { method: 'POST', body: { inputs }, signal })

/** POST that returns a file; triggers a browser download. */
export async function download(path, body, fallbackName) {
  let res
  try {
    res = await fetch(API_BASE + path, {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the Cable-N server.')
  }
  if (!res.ok) throw await parseError(res)
  const blob = await res.blob()
  const cd = res.headers.get('content-disposition') || ''
  const name = /filename="?([^";]+)"?/.exec(cd)?.[1] || fallbackName
  saveBlob(blob, name)
  return { hash: res.headers.get('x-input-hash'), number: res.headers.get('x-report-number') }
}

export function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export function saveJson(obj, name) {
  saveBlob(new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' }), name)
}

/** Polls a background job until it ends. onProgress(job) is called on every poll. */
export async function pollJob(jobId, onProgress, { signal, interval = 350 } = {}) {
  for (;;) {
    if (signal?.aborted) {
      await api(`/jobs/${jobId}/cancel`, { method: 'POST' }).catch(() => {})
      throw new DOMException('cancelled', 'AbortError')
    }
    const j = await api(`/jobs/${jobId}`)
    onProgress?.(j)
    if (j.status === 'completed' || j.status === 'cancelled') return j
    if (j.status === 'failed') throw new ApiError(422, j.error || 'The job failed')
    await new Promise((r) => setTimeout(r, interval))
  }
}
