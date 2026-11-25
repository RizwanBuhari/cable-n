// Shared UI building blocks, styled by the Track-N-derived design system.
import { useEffect, useId, useRef, useState } from 'react'
import { Icon } from './icons'

export function PageHeader({ icon, title, hint, actions, tone = 'brand' }) {
  return (
    <div className="page-header">
      <div className="page-head-left">
        {icon && <span className={`page-lead tone-${tone}`}>{icon}</span>}
        <div>
          <h1 className="page-title">{title}</h1>
          {hint && <p className="page-hint">{hint}</p>}
        </div>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function Panel({ title, icon, tone = 'brand', count, actions, children, className = '', bodyClass = 'panel-body' }) {
  return (
    <section className={`panel panel-static ${className}`}>
      {title && (
        <div className="panel-header">
          {icon && <span className={`panel-lead tone-${tone}`}>{icon}</span>}
          <h2 className="panel-title">{title}</h2>
          {count !== undefined && <span className="panel-count">{count}</span>}
          {actions}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

export function Modal({ title, onClose, children, wide, footer }) {
  const ref = useRef(null)
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    ref.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal-card ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

export function Tabs({ tabs, value, onChange, small }) {
  return (
    <div className={`tabs ${small ? 'tabs-sm' : ''}`} role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id}
          className={`tab ${value === t.id ? 'tab-active' : ''}`} onClick={() => onChange(t.id)}>
          {t.label}
          {t.badge !== undefined && t.badge !== null && <span className={`tab-badge ${t.badgeTone ? `tone-${t.badgeTone}` : ''}`}>{t.badge}</span>}
        </button>
      ))}
    </div>
  )
}

/** Tooltip on hover/focus for technical symbols. */
export function Tip({ text, children }) {
  return (
    <span className="tip" tabIndex={0}>
      {children ?? <span className="tip-i">i</span>}
      <span className="tip-box" role="tooltip">{text}</span>
    </span>
  )
}

export function Field({ label, unit, hint, tip, error, children, wide }) {
  return (
    <label className={`field ${error ? 'field-error' : ''} ${wide ? 'field-wide' : ''}`}>
      <span className="field-label">
        {label}
        {tip && <Tip text={tip} />}
      </span>
      <span className="field-control">
        {children}
        {unit && <span className="field-unit">{unit}</span>}
      </span>
      {error ? <span className="field-msg">{error}</span> : hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

/** Numeric input keeping the raw text while typing; reports number | null. */
export function NumInput({ value, onChange, min, max, step = 'any', placeholder, ...rest }) {
  const [text, setText] = useState(value ?? '')
  useEffect(() => {
    if ((value ?? '') !== (text === '' ? '' : Number(text))) setText(value ?? '')
  }, [value]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <input type="number" inputMode="decimal" value={text} min={min} max={max} step={step} placeholder={placeholder}
      onChange={(e) => {
        setText(e.target.value)
        onChange(e.target.value === '' ? null : Number(e.target.value))
      }} {...rest} />
  )
}

export function Choice({ value, onChange, options, name }) {
  const id = useId()
  return (
    <div className="choice" role="radiogroup">
      {options.map((o) => (
        <button type="button" key={String(o.value)} role="radio" aria-checked={value === o.value} name={name || id}
          className={`choice-opt ${value === o.value ? 'choice-on' : ''}`} onClick={() => onChange(o.value)}>
          <span className="choice-title">{o.label}</span>
          {o.hint && <span className="choice-hint">{o.hint}</span>}
        </button>
      ))}
    </div>
  )
}

export function Toggle({ checked, onChange, label }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle-track"><span className="toggle-dot" /></span>
      <span>{label}</span>
    </label>
  )
}

const STATUS_TONE = {
  PASS: 'good', OK: 'good', ok: 'good', feasible: 'good', rated: 'good', ADEQUATE: 'good', completed: 'good',
  FAIL: 'alert', OVERLOAD: 'alert', no_solution: 'alert', sc_fail: 'alert', ERROR: 'alert', REVIEW: 'warn',
  OUTSIDE_TOLERANCE: 'alert', over_temperature: 'alert', overload: 'alert',
  KNOWN_GAPS: 'warn', WARNING: 'warn', partial: 'warn', NOT_CHECKED: 'neutral', INFO: 'info', invalid: 'warn',
}
const STATUS_LABEL = {
  NOT_CHECKED: 'Not checked', OUTSIDE_TOLERANCE: 'Outside tolerance', KNOWN_GAPS: 'Known gaps', no_solution: 'No solution',
  sc_fail: 'SC fail', ok: 'OK', feasible: 'Feasible', partial: 'Partial', over_temperature: 'Over temperature',
  rated: 'Rated', overload: 'Overload', invalid: 'Invalid input', REVIEW: 'Review',
}
/** Engineering status - fixed semantic colours, independent of the accent. */
export function StatusBadge({ status, label }) {
  if (!status) return <span className="badge tone-neutral">—</span>
  return (
    <span className={`badge status-${STATUS_TONE[status] || 'neutral'}`}>
      <span className="badge-dot" />
      {label || STATUS_LABEL[status] || status}
    </span>
  )
}

export function Notice({ tone = 'warn', icon, children }) {
  return (
    <div className={`notice notice-${tone}`}>
      {icon ?? (tone === 'info' ? Icon.info : Icon.alert)}
      <div>{children}</div>
    </div>
  )
}

export function ErrorBox({ error }) {
  if (!error) return null
  const errs = error.errors || []
  return (
    <div className="error" role="alert">
      <strong>{error.message || String(error)}</strong>
      {errs.length > 0 && errs[0] !== error.message && (
        <ul className="error-list">{errs.slice(0, 12).map((e, i) => <li key={i}>{e}</li>)}</ul>
      )}
    </div>
  )
}

export function Spinner({ light }) {
  return <span className={`spinner ${light ? 'spinner-light' : ''}`} aria-hidden="true" />
}

export function PageLoader() {
  return (
    <div className="page-loader" aria-label="Loading">
      <div className="page-spinner" />
    </div>
  )
}

export function EmptyState({ icon = Icon.coffee, children, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">{icon}</span>
      <div>{children}</div>
      {action}
    </div>
  )
}

export function KV({ rows }) {
  return (
    <dl className="kv-list">
      {rows.filter(Boolean).map(([k, v, tip]) => (
        <div key={k}>
          <dt>{k}{tip && <Tip text={tip} />}</dt>
          <dd>{v ?? '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Stepper({ steps, current, onStep, maxReached }) {
  return (
    <ol className="stepper">
      {steps.map((s, i) => (
        <li key={s} className={`step ${i === current ? 'step-current' : ''} ${i < current ? 'step-done' : ''}`}>
          <button type="button" disabled={i > maxReached} onClick={() => onStep(i)}>
            <span className="step-num">{i < current ? '✓' : i + 1}</span>
            <span className="step-label">{s}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}

export function Collapsible({ title, children, defaultOpen = false, right }) {
  return (
    <details className="collapsible" open={defaultOpen}>
      <summary>
        <span>{title}</span>
        {right}
      </summary>
      <div className="collapsible-body">{children}</div>
    </details>
  )
}

export function StatTile({ label, value, hint, tone = 'brand', icon }) {
  return (
    <div className={`stat-tile tone-${tone}`}>
      {icon && <div className="stat-top"><span className="stat-icon">{icon}</span></div>}
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function ProgressBar({ done, total, label }) {
  const pct = total ? Math.round((done / total) * 100) : null
  return (
    <div className="progress" role="progressbar" aria-valuenow={done} aria-valuemax={total || undefined}>
      <div className="progress-track">
        <div className={`progress-fill ${pct === null ? 'progress-indeterminate' : ''}`} style={pct === null ? undefined : { width: `${pct}%` }} />
      </div>
      <span className="progress-label">{label ?? (total ? `${done} of ${total}` : 'Starting…')}</span>
    </div>
  )
}

export const VERIFY_TEXT = 'Results come from a deterministic calculation engine and the inputs shown. Passing these numerical checks is not design approval — a qualified electrical engineer must verify the design against the applicable standards and local requirements before use.'

export function VerificationNotice({ compact }) {
  return (
    <div className={`verify-notice ${compact ? 'verify-compact' : ''}`}>
      {Icon.shield}
      <div><strong>Engineering verification required.</strong> {VERIFY_TEXT}</div>
    </div>
  )
}
