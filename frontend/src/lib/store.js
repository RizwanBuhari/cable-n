// Everything a visitor saves stays in THIS browser:
//  * IndexedDB  - saved calculations (inputs + engine results), projects,
//                 templates, custom cables (larger quota than localStorage)
//  * localStorage - preferences, drafts, consent
// Nothing is synchronised between devices. Users can export/import JSON.
import { useEffect, useState, useSyncExternalStore } from 'react'

const DB_NAME = 'cable-n'
const DB_VERSION = 1
export const STORES = ['calculations', 'projects', 'templates', 'cables']
let dbPromise = null

function openDb() {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    if (!('indexedDB' in window)) return reject(new Error('This browser cannot store data locally (IndexedDB unavailable).'))
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      for (const s of STORES) if (!req.result.objectStoreNames.contains(s)) req.result.createObjectStore(s, { keyPath: 'id' })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return dbPromise
}

function tx(store, mode, fn) {
  return openDb().then((db) => new Promise((resolve, reject) => {
    const t = db.transaction(store, mode)
    const s = t.objectStore(store)
    const out = fn(s)
    t.oncomplete = () => resolve(out?.result ?? out)
    t.onerror = () => reject(t.error)
    t.onabort = () => reject(t.error || new Error('Storage quota exceeded?'))
  }))
}

const listeners = new Set()
let version = 0
function changed() {
  version += 1
  listeners.forEach((l) => l())
}

export const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)

export const db = {
  all: (store) => tx(store, 'readonly', (s) => s.getAll()),
  get: (store, id) => tx(store, 'readonly', (s) => s.get(id)),
  async put(store, item) {
    const now = new Date().toISOString()
    const rec = { ...item, id: item.id || uid(), createdAt: item.createdAt || now, updatedAt: now }
    await tx(store, 'readwrite', (s) => s.put(rec))
    changed()
    return rec
  },
  async remove(store, id) {
    await tx(store, 'readwrite', (s) => s.delete(id))
    changed()
  },
  async clear(store) {
    await tx(store, 'readwrite', (s) => s.clear())
    changed()
  },
}

/** React hook: live list from a store, newest first. */
export function useStore(store) {
  const v = useSyncExternalStore((l) => (listeners.add(l), () => listeners.delete(l)), () => version)
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    let live = true
    db.all(store)
      .then((xs) => live && setItems(xs.sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''))))
      .catch((e) => live && (setError(e.message), setItems([])))
    return () => { live = false }
  }, [store, v])
  return { items, error }
}

// ---------------------------------------------------------------- preferences
const PREF_KEY = 'cableNPrefs'
export const DEFAULT_PREFS = {
  engineering: {
    voltage_drop_limit_pct: 5, power_factor: 0.85, soil_temp: 30, air_temp: 40, soil_resistivity: 1.5,
    duct_resistivity: 1.2, depth: 0.8, fault_time: 1, fault_share: 'equal',
  },
  report: { prepared_by: '', checked_by: '', kind: 'detailed' },
}

export function getPrefs() {
  try {
    const p = JSON.parse(localStorage.getItem(PREF_KEY) || '{}')
    return { engineering: { ...DEFAULT_PREFS.engineering, ...p.engineering }, report: { ...DEFAULT_PREFS.report, ...p.report } }
  } catch {
    return DEFAULT_PREFS
  }
}
export function setPrefs(p) {
  localStorage.setItem(PREF_KEY, JSON.stringify(p))
  changed()
}

// ---------------------------------------------------------------- drafts (autosave)
export const drafts = {
  get(key) {
    try { return JSON.parse(localStorage.getItem(`cableNDraft:${key}`)) } catch { return null }
  },
  set(key, data) {
    try { localStorage.setItem(`cableNDraft:${key}`, JSON.stringify({ data, savedAt: new Date().toISOString() })) } catch { /* quota */ }
  },
  clear(key) { localStorage.removeItem(`cableNDraft:${key}`) },
}

// ---------------------------------------------------------------- export / import / clear
export async function exportAll() {
  const out = { format: 'cable-n-export', version: 1, exportedAt: new Date().toISOString(), prefs: getPrefs() }
  for (const s of STORES) out[s] = await db.all(s)
  return out
}

export async function importAll(data, { replace = false } = {}) {
  if (!data || (data.format !== 'cable-n-export' && data.format !== 'cable-n-calculation')) {
    throw new Error('This file is not a Cable-N export.')
  }
  if (data.format === 'cable-n-calculation') {
    await db.put('calculations', { ...data.calculation, id: undefined })
    return { calculations: 1 }
  }
  const counts = {}
  for (const s of STORES) {
    if (!Array.isArray(data[s])) continue
    if (replace) await db.clear(s)
    for (const item of data[s]) await db.put(s, item)
    counts[s] = data[s].length
  }
  if (data.prefs) setPrefs(data.prefs)
  return counts
}

export async function clearAll() {
  for (const s of STORES) await db.clear(s)
  Object.keys(localStorage).filter((k) => k.startsWith('cableN')).forEach((k) => localStorage.removeItem(k))
  changed()
}

export async function storageEstimate() {
  try {
    const e = await navigator.storage?.estimate?.()
    return e ? { used: e.usage, quota: e.quota } : null
  } catch {
    return null
  }
}
