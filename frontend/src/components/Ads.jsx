// Google AdSense, strictly optional and non-intrusive:
//  * nothing loads unless VITE_ADS_ENABLED=true and a valid publisher ID is set;
//  * with the built-in consent banner ("own" CMP), the AdSense script is only
//    injected after the visitor accepts advertising cookies; with Google's
//    certified CMP ("google"), Google's own message handles consent;
//  * slots are lazy - the ad request happens when the slot scrolls into view;
//  * a slot that Google leaves unfilled collapses completely;
//  * a valid ad-free licence hides every slot;
//  * slots are only placed in side rails / below content - never over results.
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { ADS, getConsent, getLicence } from '../lib/prefs'

const AdCtx = createContext({ allowed: false })

let scriptPromise = null
function loadAdSense() {
  if (scriptPromise) return scriptPromise
  scriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.async = true
    s.crossOrigin = 'anonymous'
    s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(ADS.client)}`
    s.onload = resolve
    s.onerror = () => reject(new Error('blocked'))
    document.head.appendChild(s)
  })
  return scriptPromise
}

function computeAllowed() {
  if (!ADS.enabled) return false
  const lic = getLicence()
  if (lic?.ad_free && (!lic.expires || new Date(lic.expires) >= new Date())) return false
  if (ADS.cmp === 'google') return true
  return !!getConsent()?.ads
}

export function AdProvider({ children }) {
  const [allowed, setAllowed] = useState(computeAllowed)
  useEffect(() => {
    const upd = () => setAllowed(computeAllowed())
    window.addEventListener('cablen-consent', upd)
    window.addEventListener('cablen-licence', upd)
    return () => {
      window.removeEventListener('cablen-consent', upd)
      window.removeEventListener('cablen-licence', upd)
    }
  }, [])
  return <AdCtx.Provider value={{ allowed }}>{children}</AdCtx.Provider>
}

export function useAds() {
  return useContext(AdCtx)
}

/** A responsive, lazily loaded, clearly labelled sponsored slot. */
export function AdSlot({ slot = 'rail', className = '' }) {
  const { allowed } = useAds()
  const ref = useRef(null)
  const insRef = useRef(null)
  const [state, setState] = useState('idle') // idle | loading | filled | empty
  const id = ADS.slots[slot]

  useEffect(() => {
    if (!allowed || !id || !ref.current) return undefined
    let pushed = false
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting) || pushed) return
      pushed = true
      io.disconnect()
      setState('loading')
      loadAdSense()
        .then(() => {
          try { (window.adsbygoogle = window.adsbygoogle || []).push({}) } catch { setState('empty') }
        })
        .catch(() => setState('empty')) // ad blocker or network: hide quietly
    }, { rootMargin: '200px' })
    io.observe(ref.current)
    // AdSense sets data-ad-status="filled" | "unfilled" on the <ins>
    const mo = new MutationObserver(() => {
      const st = insRef.current?.getAttribute('data-ad-status')
      if (st === 'filled') setState('filled')
      if (st === 'unfilled') setState('empty')
    })
    if (insRef.current) mo.observe(insRef.current, { attributes: true, attributeFilter: ['data-ad-status'] })
    return () => { io.disconnect(); mo.disconnect() }
  }, [allowed, id])

  if (!allowed || !id) return null
  return (
    <aside ref={ref} className={`ad-slot ${slot === 'inline' ? 'ad-inline' : ''} ${className}`} hidden={state === 'empty'}
      aria-label="Sponsored content">
      <span className="ad-label">Sponsored</span>
      <ins ref={insRef} className="adsbygoogle" style={{ display: 'block' }} data-ad-client={ADS.client}
        data-ad-slot={id} data-ad-format={slot === 'rail' ? 'auto' : 'horizontal'} data-full-width-responsive="true" />
    </aside>
  )
}

/** Page body with a right-hand rail for a sponsored slot (stacks on mobile). */
export function WithRail({ children, rail }) {
  const { allowed } = useAds()
  if (!allowed && !rail) return <>{children}</>
  return (
    <div className="with-rail">
      <div>{children}</div>
      <div className="rail">
        {rail}
        <AdSlot slot="rail" />
      </div>
    </div>
  )
}
