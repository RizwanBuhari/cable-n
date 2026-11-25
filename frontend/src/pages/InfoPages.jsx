import { Link } from 'react-router-dom'
import { WithRail } from '../components/Ads'
import { openConsent } from '../components/Consent'
import { Icon } from '../components/icons'
import { EmptyState, PageHeader } from '../components/ui'
import { ADS, CONTACT_EMAIL } from '../lib/prefs'

const UPDATED = 'November 2026'

function About() {
  return (
    <article className="prose">
      <p><b>Cable-N — Cable Sizing &amp; Engineering Intelligence</b> is a free, public engineering website for sizing and verifying power cables.</p>
      <h2>What it does</h2>
      <ul>
        <li><Link to="/calculators/single-feeder">Single feeder sizing</Link> with every single- and parallel-run option.</li>
        <li><Link to="/calculators/batch">Batch cable schedules</Link> with Excel import and export.</li>
        <li><Link to="/calculators/current-rating">Current-rating verification</Link> of duct banks and buried groups.</li>
        <li><Link to="/calculators/advanced-mv-hv">Full IEC 60287 / 60949 MV/HV analysis</Link> with mutual heating, losses, short-circuit and emergency ratings.</li>
      </ul>
      <h2>The calculation engine</h2>
      <p>All numbers come from one deterministic Python engine. The website runs the original engineering program's own functions and tables; automated tests drive the original program through its terminal dialogues and require the website to reproduce its numbers exactly. The engine's benchmark cases are published, with their deviations, in the <Link to="/validation">Validation centre</Link>.</p>
      <h2>Your data</h2>
      <p>No account is needed. The server computes each request and keeps nothing. Anything you save stays in your own browser. See the <Link to="/privacy">privacy policy</Link>.</p>
      <h2>Not an approval</h2>
      <p>Cable-N supports qualified engineers; it does not replace their judgement or a formal design review. Read the <Link to="/disclaimer">engineering disclaimer</Link>.</p>
    </article>
  )
}

function Contact() {
  return (
    <article className="prose">
      {CONTACT_EMAIL ? <p>Questions, bug reports or corrections: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</p>
        : <p>A contact address has not been published for this deployment yet.</p>}
      <p>When reporting a calculation issue, attach the JSON export of the calculation (any result → JSON) so it can be reproduced exactly. Please do not send confidential client information.</p>
    </article>
  )
}

function Privacy() {
  return (
    <article className="prose">
      <p><i>Last updated {UPDATED}.</i></p>
      <h2>Summary</h2>
      <ul>
        <li>No accounts, no sign-up, no server-side database of your calculations.</li>
        <li>Calculation inputs are sent to our server only to be computed (and, for reports, to build the file); they are not stored, logged as content, or shared.</li>
        <li>Saved work, preferences and drafts are kept in your browser's local storage (IndexedDB / localStorage) on your device.</li>
      </ul>
      <h2>What the server processes</h2>
      <p>Each request carries the inputs needed for that calculation. The server returns the result and discards the inputs. PDF reports are generated in a temporary folder that is deleted immediately after sending. Uploaded Excel files and datasheet PDFs are read in memory and discarded. To protect the service from abuse, your IP address is held in memory for rate limiting (a minute for request limits, a day for assistant limits) and in standard web-server access logs operated by the host.</p>
      <h2>Local storage</h2>
      <p>Your saved calculations, projects, templates, custom cables, drafts, accent colour and cookie choice are stored only in your browser. You can export, import or delete them under <Link to="/settings">Settings</Link>. They are not synchronised between devices.</p>
      <h2>Optional AI assistant</h2>
      <p>If the assistant is enabled on this site, your question is sent to the configured AI provider (Google Gemini). A calculation is included only when you tick “Share the current calculation”; the server then sends the recomputed inputs and results — never project, client or site names. Do not enter confidential information in the assistant.</p>
      <h2>Advertising</h2>
      {ADS.enabled ? (
        <p>This site is supported by Google AdSense. With your consent, Google and its partners may use cookies or similar identifiers to show and measure ads; without consent no advertising script is loaded{ADS.cmp === 'google' ? ' (consent is managed by Google\'s certified consent message)' : ''}. Learn how Google uses data at <a href="https://policies.google.com/technologies/partner-sites" rel="noopener noreferrer" target="_blank">policies.google.com/technologies/partner-sites</a>. <button className="table-link" style={{ border: 0, background: 'none', cursor: 'pointer' }} onClick={openConsent}>Change your choice</button>.</p>
      ) : <p>This deployment shows no advertising and sets no advertising or analytics cookies.</p>}
      <h2>Your rights</h2>
      <p>Because we do not keep personal data beyond transient logs and rate-limit counters, most requests can be satisfied by clearing your browser's site data. For anything else, see the <Link to="/contact">contact page</Link>.</p>
    </article>
  )
}

function Terms() {
  return (
    <article className="prose">
      <p><i>Last updated {UPDATED}.</i></p>
      <h2>Use of the service</h2>
      <p>Cable-N is provided free of charge, “as is”, without warranty of any kind. You may use the calculators for your own engineering work, including commercial projects, subject to the <Link to="/disclaimer">engineering disclaimer</Link>.</p>
      <h2>Acceptable use</h2>
      <p>Do not attempt to overload, scrape at scale, probe or disrupt the service. Automated use is limited by rate limits; contact us for heavier use.</p>
      <h2>Responsibility for results</h2>
      <p>You are responsible for your inputs, for checking results, and for any decision based on them. Results must be verified by a qualified electrical engineer against applicable standards, manufacturer data and local authority requirements.</p>
      <h2>Liability</h2>
      <p>To the maximum extent permitted by law, the operators of Cable-N are not liable for any loss or damage arising from use of the website or its results.</p>
      <h2>Changes</h2>
      <p>The calculation engine, features and these terms may change. Reports carry the engine version used.</p>
    </article>
  )
}

function Disclaimer() {
  return (
    <article className="prose">
      <p><b>Cable-N is an engineering calculation aid. It does not certify, approve or guarantee any design.</b></p>
      <ul>
        <li>A result that passes the numerical checks shown is <i>not</i> design approval and does not confirm compliance with any standard, code or authority requirement.</li>
        <li>Calculations use generic tabulated data and the methods implemented in the engine, with documented approximations (for example the PVC correction, nearest-value table lookups, the multi-bank Mode 4 estimate and the screened three-core limitations listed in the <Link to="/resources">resources</Link>).</li>
        <li>Built-in cable data is generic and is not any manufacturer's product data. Presets are illustrative.</li>
        <li>Validation cases compare the engine with values quoted in its source program; Cable-N has not independently verified those references and passing them is not certification or equivalence with any commercial software.</li>
        <li>AI assistant answers are explanations only and may be wrong; they never change or approve a calculation.</li>
      </ul>
      <p>Every design must be reviewed and approved by a qualified electrical engineer before construction or procurement.</p>
    </article>
  )
}

const PAGES = {
  about: ['About Cable-N', Icon.info, About], contact: ['Contact', Icon.mail, Contact], privacy: ['Privacy policy', Icon.shield, Privacy],
  terms: ['Terms of service', Icon.file, Terms], disclaimer: ['Engineering disclaimer', Icon.alert, Disclaimer],
}

export default function InfoPages({ page }) {
  if (page === 'notfound') return <EmptyState icon={Icon.search}>Page not found. <Link className="table-link" to="/">Go to the home page</Link></EmptyState>
  const [title, icon, Body] = PAGES[page]
  return <WithRail><PageHeader icon={icon} title={title} /><Body /></WithRail>
}
