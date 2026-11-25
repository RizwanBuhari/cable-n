// Accent colour, consent, ads and page metadata helpers.
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { routeMeta, SITE_NAME } from '../seo/routes'

// ---------------------------------------------------------------- accent colour
// Personal, per-browser accent layered on the brand system. Engineering status
// colours (PASS/FAIL/WARNING) never follow it.
export const ACCENT_SWATCHES = [
  { id: 'cable-red', label: 'Cable-N Red', base: '#ce1b28', hover: '#b0151f', soft: '#fdecee' },
  { id: 'ocean-blue', label: 'Ocean Blue', base: '#1d4ed8', hover: '#1741b0', soft: '#e8effd' },
  { id: 'forest-green', label: 'Forest Green', base: '#15803d', hover: '#116830', soft: '#e7f6e8' },
  { id: 'royal-purple', label: 'Royal Purple', base: '#7c3aed', hover: '#6527c9', soft: '#f1e9fe' },
  { id: 'sunset-orange', label: 'Sunset Orange', base: '#c2410c', hover: '#9d350a', soft: '#fdece0' },
]
const ACCENT_KEY = 'cableNAccentColor'

export function getStoredAccentId() {
  try { return localStorage.getItem(ACCENT_KEY) || ACCENT_SWATCHES[0].id } catch { return ACCENT_SWATCHES[0].id }
}
export function applyAccentColor(id) {
  const s = ACCENT_SWATCHES.find((x) => x.id === id) || ACCENT_SWATCHES[0]
  const r = document.documentElement.style
  r.setProperty('--brand-red', s.base)
  r.setProperty('--brand-red-hover', s.hover)
  r.setProperty('--brand-red-soft', s.soft)
  try { localStorage.setItem(ACCENT_KEY, s.id) } catch { /* ignore */ }
}

// ---------------------------------------------------------------- consent
const CONSENT_KEY = 'cableNConsent'
export const CONSENT_VERSION = 1
export function getConsent() {
  try {
    const c = JSON.parse(localStorage.getItem(CONSENT_KEY))
    return c && c.v === CONSENT_VERSION ? c : null
  } catch { return null }
}
export function setConsent(ads) {
  const c = { v: CONSENT_VERSION, ads: !!ads, at: new Date().toISOString() }
  localStorage.setItem(CONSENT_KEY, JSON.stringify(c))
  window.dispatchEvent(new CustomEvent('cablen-consent', { detail: c }))
  return c
}

// ---------------------------------------------------------------- ads configuration (public build values)
const env = import.meta.env
export const ADS = {
  enabled: env.VITE_ADS_ENABLED === 'true' && /^ca-pub-\d{10,20}$/.test((env.VITE_ADSENSE_CLIENT || '').trim()),
  client: (env.VITE_ADSENSE_CLIENT || '').trim(),
  slots: { rail: (env.VITE_ADSENSE_SLOT_RAIL || '').trim(), inline: (env.VITE_ADSENSE_SLOT_INLINE || '').trim() },
  cmp: env.VITE_ADSENSE_CMP === 'google' ? 'google' : 'own',
}
const LICENCE_KEY = 'cableNAdFreeLicence'
export function getLicence() {
  try { return JSON.parse(localStorage.getItem(LICENCE_KEY)) } catch { return null }
}
export function setLicence(v) {
  if (v) localStorage.setItem(LICENCE_KEY, JSON.stringify(v))
  else localStorage.removeItem(LICENCE_KEY)
  window.dispatchEvent(new Event('cablen-licence'))
}
export const CONTACT_EMAIL = (env.VITE_CONTACT_EMAIL || '').trim()
export const SITE_URL = (env.VITE_SITE_URL || '').replace(/\/$/, '')

// ---------------------------------------------------------------- page metadata
function setMeta(attr, key, value) {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', value)
}

/** Sets <title>, description, canonical and OG tags for the current route. */
export function usePageMeta(override) {
  const { pathname } = useLocation()
  useEffect(() => {
    const m = override || routeMeta(pathname) || { title: SITE_NAME, description: '' }
    document.title = m.title
    if (m.description) {
      setMeta('name', 'description', m.description)
      setMeta('property', 'og:description', m.description)
    }
    setMeta('property', 'og:title', m.title)
    const url = (SITE_URL || window.location.origin) + pathname
    setMeta('property', 'og:url', url)
    let link = document.head.querySelector('link[rel="canonical"]')
    if (!link) {
      link = document.createElement('link')
      link.setAttribute('rel', 'canonical')
      document.head.appendChild(link)
    }
    link.setAttribute('href', url)
  }, [pathname, override?.title, override?.description])
}
