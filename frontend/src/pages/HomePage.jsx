import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { WithRail } from '../components/Ads'
import { Icon } from '../components/icons'
import LogoShine from '../components/LogoShine'
import { api } from '../lib/api'

export const MODES = [
  { n: 1, to: '/calculators/single-feeder', title: 'Single feeder sizing', icon: Icon.cable,
    text: 'Design current from A, kW, kVA, MW or MVA; derating for ambient, soil, depth and grouping; voltage drop; short-circuit withstand; every single-run and parallel-run option.' },
  { n: 2, to: '/calculators/batch', title: 'Batch cable schedule', icon: Icon.layers,
    text: 'Size dozens of feeders at once from a table or Excel template. Invalid rows are flagged individually and never corrupt the valid ones.' },
  { n: 3, to: '/calculators/current-rating', title: 'Current-rating verification', icon: Icon.grid,
    text: 'Check an existing duct bank or buried group: mixed single-core and 3-core positions, up to three banks, grouping and inter-bank factors.' },
  { n: 4, to: '/calculators/advanced-mv-hv', title: 'Advanced MV/HV analysis', icon: Icon.thermo,
    text: 'Full IEC 60287 / 60949: T1–T4, AC resistance, sheath and armour losses, mutual heating, sequence impedance, induced voltage, short-circuit and emergency ratings.' },
]

function HeroArt() {
  const wires = Array.from({ length: 36 }, (_, i) => {
    const a = (i / 36) * Math.PI * 2
    return <circle key={i} cx={160 + 124 * Math.cos(a)} cy={160 + 124 * Math.sin(a)} r="5.2" fill="#d9a0a5" opacity="0.55" />
  })
  const cores = [-90, 30, 150].map((d) => {
    const a = (d * Math.PI) / 180
    return { x: 160 + 52 * Math.cos(a), y: 166 + 52 * Math.sin(a) }
  })
  return (
    <svg className="hero-art" viewBox="0 0 320 320" aria-hidden="true">
      <circle cx="160" cy="160" r="150" fill="#CE1B28" opacity="0.92" />
      <g className="hero-ring">{wires}</g>
      <circle cx="160" cy="160" r="112" fill="#2b2322" opacity="0.55" />
      {cores.map((c, i) => (
        <g key={i}>
          <circle cx={c.x} cy={c.y} r="44" fill="#f4f5f6" />
          <circle cx={c.x} cy={c.y} r="38" fill="none" stroke="#c9ccd0" strokeWidth="2" />
          <circle cx={c.x} cy={c.y} r="20" fill="#212121" />
          <circle cx={c.x - 6} cy={c.y - 6} r="5" fill="#fff" opacity="0.18" />
        </g>
      ))}
    </svg>
  )
}

export default function HomePage() {
  const [health, setHealth] = useState(null)
  useEffect(() => { api('/health').then(setHealth).catch(() => setHealth({ status: 'down' })) }, [])
  return (
    <WithRail>
      <section className="home-hero">
        <div>
          <LogoShine src="/brand/cable-n-logo-full-on-dark.svg" alt="Cable-N — Cable Sizing & Engineering Intelligence" shine="dark" imgClassName="hero-logo" />
          <h1>Cable sizing you can trace, check and explain.</h1>
          <p>
            Cable-N sizes and verifies power cables with a deterministic engineering engine: derating chains,
            voltage drop, short-circuit withstand and full IEC 60287 thermal analysis — every intermediate value shown,
            every report traceable. Free to use, no account required.
          </p>
          <div className="hero-actions">
            <Link to="/calculators/single-feeder" className="btn-primary">{Icon.play} Start a calculation</Link>
            <Link to="/resources" className="btn-ghost-light">{Icon.book} How it works</Link>
          </div>
        </div>
        <HeroArt />
      </section>

      <h2 className="section-title">Four engineering calculators</h2>
      <div className="mode-grid">
        {MODES.map((m) => (
          <Link key={m.to} to={m.to} className="mode-card">
            <span className="stat-icon tone-brand" style={{ background: 'var(--brand-red-soft)', color: 'var(--brand-red)' }}>{m.icon}</span>
            <span className="mode-num">Mode {m.n}</span>
            <h3>{m.title}</h3>
            <p>{m.text}</p>
            <span className="mode-go">Open calculator {Icon.arrowRight}</span>
          </Link>
        ))}
      </div>

      <h2 className="section-title">Built for engineering work, not guesswork</h2>
      <div className="feature-grid">
        <div className="feature">
          <span className="stat-icon tone-good">{Icon.shield}</span>
          <h4>One engine, verified</h4>
          <p>All four modes run the same Python calculation engine. Automated tests prove the website gives exactly the numbers of the original program.</p>
        </div>
        <div className="feature">
          <span className="stat-icon tone-info">{Icon.ruler}</span>
          <h4>Every step visible</h4>
          <p>Correction factors, governing constraints, rejected sizes, thermal resistances and losses — nothing is hidden behind a single answer.</p>
        </div>
        <div className="feature">
          <span className="stat-icon tone-warn">{Icon.file}</span>
          <h4>Reports that trace back</h4>
          <p>PDF, Excel, CSV and JSON. Each report carries the engine version and a fingerprint of the exact inputs used.</p>
        </div>
        <div className="feature">
          <span className="stat-icon tone-neutral">{Icon.save}</span>
          <h4>Private by design</h4>
          <p>No sign-up. Saved calculations, projects and templates stay in your browser; the server computes and forgets.</p>
        </div>
      </div>

      <div className="verify-notice mt-16">
        {Icon.alert}
        <div>
          <strong>Engineering tool, not an approval.</strong> Cable-N supports qualified engineers. Results must be verified
          against the applicable standards, manufacturer data and local authority requirements before use.{' '}
          <Link to="/disclaimer" className="table-link">Read the disclaimer</Link>.
          {health && (
            <span className="muted"> Engine status: {health.status === 'ok' ? 'online' : 'unavailable'}{health.engine_version ? ` · ${health.engine_version}` : ''}.</span>
          )}
        </div>
      </div>
    </WithRail>
  )
}
