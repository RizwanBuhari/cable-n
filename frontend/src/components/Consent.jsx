// Cookie / storage consent. Cable-N itself sets no tracking cookies; the
// only optional third party is advertising. Essential local storage (your
// saved work and preferences) needs no consent because it is what you asked
// for and never leaves the browser.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ADS, getConsent, setConsent } from '../lib/prefs'
import { Icon } from './icons'

export function openConsent() {
  window.dispatchEvent(new Event('cablen-open-consent'))
}

export default function ConsentBanner() {
  const needs = ADS.enabled && ADS.cmp === 'own'
  const [open, setOpen] = useState(() => needs && !getConsent())
  useEffect(() => {
    const show = () => setOpen(true)
    window.addEventListener('cablen-open-consent', show)
    return () => window.removeEventListener('cablen-open-consent', show)
  }, [])
  if (!open) return null
  const choose = (ads) => {
    setConsent(ads)
    setOpen(false)
  }
  return (
    <div className="consent" role="dialog" aria-label="Cookie preferences">
      {Icon.cookie}
      <div>
        {needs ? (
          <p>
            Cable-N is free and funded by advertising. With your permission our advertising partner (Google AdSense)
            may use cookies to show and measure ads. Your calculations never leave your browser except to be computed,
            and are not shared with advertisers. <Link to="/privacy" className="table-link">Privacy policy</Link>
          </p>
        ) : (
          <p>
            Cable-N uses no advertising or tracking cookies on this site. Your saved work stays in this browser's local
            storage. <Link to="/privacy" className="table-link">Privacy policy</Link>
          </p>
        )}
        <div className="row-actions">
          {needs ? (
            <>
              <button className="btn-primary" onClick={() => choose(true)}>Accept advertising cookies</button>
              <button className="btn-outline" onClick={() => choose(false)}>Essential only</button>
            </>
          ) : (
            <button className="btn-primary" onClick={() => setOpen(false)}>OK</button>
          )}
        </div>
      </div>
    </div>
  )
}
