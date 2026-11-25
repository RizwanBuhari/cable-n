// Site shell - Track-N's two-level header (red utility strip + white nav bar
// with the animated logo), page content, footer, consent banner, assistant.
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { usePageMeta } from '../lib/prefs'
import ChatPanel from './ChatPanel'
import ConsentBanner, { openConsent } from './Consent'
import { Icon } from './icons'
import LogoShine from './LogoShine'

const NAV = [
  { to: '/', label: 'Home', icon: Icon.home, end: true },
  { to: '/calculators', label: 'Calculators', icon: Icon.calc },
  { to: '/cable-library', label: 'Cable Library', icon: Icon.cable },
  { to: '/comparison', label: 'Comparison', icon: Icon.compare },
  { to: '/validation', label: 'Validation', icon: Icon.shield },
  { to: '/resources', label: 'Engineering Resources', icon: Icon.book },
  { to: '/settings', label: 'Settings', icon: Icon.settings },
  { to: '/about', label: 'About', icon: Icon.info },
]

export default function AppLayout() {
  const { pathname } = useLocation()
  const [navOpen, setNavOpen] = useState(false)
  usePageMeta()
  useEffect(() => {
    setNavOpen(false)
    window.scrollTo({ top: 0 })
  }, [pathname])

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">Skip to content</a>
      <header className="app-header">
        <div className="topstrip">
          <div className="topstrip-inner">
            <span className="topstrip-brand">Cable-N · Cable Sizing &amp; Engineering Intelligence</span>
            <div className="topstrip-right">
              <span className="topstrip-note">{Icon.shield} No sign-up · your work stays in this browser</span>
              <Link to="/calculators?tab=saved" className="topstrip-link">Saved work</Link>
            </div>
          </div>
        </div>
        <div className="topbar">
          <div className="topbar-inner">
            <NavLink to="/" className="topbar-brand" end aria-label="Cable-N home">
              <LogoShine src="/brand/cable-n-logo.svg" alt="Cable-N" shine="light" imgClassName="topbar-logo"
                fallback={<span className="topbar-fallback" style={{ display: 'none' }}>Cable-N</span>} />
            </NavLink>
            <button className="nav-toggle" aria-label="Menu" aria-expanded={navOpen} onClick={() => setNavOpen((o) => !o)}>
              {navOpen ? Icon.x : Icon.menu}
            </button>
            <nav className={`topnav ${navOpen ? 'topnav-open' : ''}`} aria-label="Main">
              {NAV.map((n) => (
                <NavLink key={n.to} to={n.to} end={n.end} title={n.label}>
                  {n.icon}
                  <span>{n.label}</span>
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="content" id="main">
        <div key={pathname} className="page-enter">
          <Outlet />
        </div>
      </main>

      <footer className="site-footer">
        <div className="site-footer-inner">
          <div className="footer-brand">
            <img src="/brand/cable-n-logo.svg" alt="Cable-N" />
            <div>Cable Sizing &amp; Engineering Intelligence. Free engineering calculators built on a validated, deterministic calculation engine.</div>
          </div>
          <div>
            <h4>Calculators</h4>
            <Link to="/calculators/single-feeder">Single feeder</Link>
            <Link to="/calculators/batch">Batch schedule</Link>
            <Link to="/calculators/current-rating">Current rating</Link>
            <Link to="/calculators/advanced-mv-hv">Advanced MV/HV</Link>
          </div>
          <div>
            <h4>Learn</h4>
            <Link to="/resources">Engineering resources</Link>
            <Link to="/validation">Validation centre</Link>
            <Link to="/cable-library">Cable library</Link>
            <Link to="/about">About</Link>
          </div>
          <div>
            <h4>Legal</h4>
            <Link to="/disclaimer">Engineering disclaimer</Link>
            <Link to="/privacy">Privacy policy</Link>
            <Link to="/terms">Terms of service</Link>
            <Link to="/contact">Contact</Link>
            <button className="footer-btn" onClick={openConsent}>Cookie preferences</button>
          </div>
          <div className="footer-legal">
            © {new Date().getFullYear()} Cable-N. Results support — and never replace — the judgement of a qualified electrical engineer.
          </div>
        </div>
      </footer>
      <ConsentBanner />
      <ChatPanel />
    </div>
  )
}
