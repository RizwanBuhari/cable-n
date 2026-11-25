import { useEffect, useRef, useState } from 'react'
import { WithRail } from '../components/Ads'
import { Icon } from '../components/icons'
import { Collapsible, ErrorBox, Modal, Notice, PageHeader, ProgressBar, Spinner, StatusBadge, Tip } from '../components/ui'
import { api, download, pollJob } from '../lib/api'
import { num, timeAgo } from '../lib/format'

const HIST = 'cableNValidationHistory'

export default function ValidationPage() {
  const [data, setData] = useState(null)
  const [results, setResults] = useState({})
  const [job, setJob] = useState(null)
  const [err, setErr] = useState(null)
  const [open, setOpen] = useState(null)
  const [hist, setHist] = useState(() => { try { return JSON.parse(localStorage.getItem(HIST)) || [] } catch { return [] } })
  const ctl = useRef(null)
  useEffect(() => { api('/validation/cases').then(setData).catch(setErr) }, [])

  async function run(ids) {
    setErr(null)
    ctl.current = new AbortController()
    try {
      const { job_id, total } = await api('/validation/run', { method: 'POST', body: { case_ids: ids } })
      setJob({ done: 0, total })
      const j = await pollJob(job_id, setJob, { signal: ctl.current.signal, interval: 400 })
      const out = Object.fromEntries(j.result.results.map((r) => [r.case_id, r]))
      setResults((x) => ({ ...x, ...out }))
      const entry = { at: new Date().toISOString(), engine: data?.engine_version, statuses: Object.fromEntries(j.result.results.map((r) => [r.case_id, r.status])) }
      const h = [entry, ...hist].slice(0, 20)
      setHist(h); localStorage.setItem(HIST, JSON.stringify(h))
    } catch (e) { if (e.name !== 'AbortError') setErr(e) } finally { setJob(null) }
  }
  const cnt = (s) => Object.values(results).filter((r) => r.status === s).length

  return (
    <WithRail>
      <PageHeader icon={Icon.shield} title="Validation centre" hint="Runs the original program's own validation routines against its reference workbook and CYMCAP benchmark cases — every deviation shown, including the ones outside tolerance."
        actions={<>
          {job ? <button className="btn-outline" onClick={() => ctl.current?.abort()}>Cancel</button> : <button className="btn-primary" onClick={() => run([])} disabled={!data}>{Icon.play} Run all</button>}
          <button className="btn-sm" onClick={() => download('/validation/report.json', null, 'cable-n-validation.json').catch(setErr)}>{Icon.download} Export JSON</button>
        </>} />
      <Notice>{data?.disclaimer || 'Benchmarks are source-provided and not independently verified.'}</Notice>
      {job && <div className="card mt-16"><ProgressBar done={job.done} total={job.total} label={`${job.done} of ${job.total} cases`} /></div>}
      <ErrorBox error={err} />
      {Object.keys(results).length > 0 && (
        <div className="stat-grid mt-16">
          {[['PASS', 'good'], ['OUTSIDE_TOLERANCE', 'alert'], ['KNOWN_GAPS', 'warn'], ['INFO', 'info'], ['ERROR', 'alert']].map(([s, t]) => cnt(s) > 0 && (
            <div key={s} className={`stat-tile status-${t}`}><div className="stat-value">{cnt(s)}</div><div className="stat-label"><StatusBadge status={s} /></div></div>
          ))}
        </div>
      )}
      {!data ? <Spinner /> : (
        <div className="table-wrap mt-16">
          <table className="data-table">
            <thead><tr><th>Case</th><th>Benchmark source</th><th>Tolerance</th><th>Status</th><th className="num">Worst headline dev.</th><th /></tr></thead>
            <tbody>
              {data.cases.map((c) => {
                const r = results[c.id]
                return (
                  <tr key={c.id}>
                    <td><b>{c.title}</b><div className="small muted mono">{c.function}</div></td>
                    <td className="small" style={{ whiteSpace: 'normal', maxWidth: 260 }}>{c.source}</td>
                    <td className="small">{[c.tolerance_pct != null && `±${c.tolerance_pct} %`, c.tolerance_K != null && `±${c.tolerance_K} K`].filter(Boolean).join(', ') || 'routine flags'} <Tip text={c.tolerance_source} /></td>
                    <td>{r ? <StatusBadge status={r.status} /> : <span className="muted small">not run</span>}</td>
                    <td className="num">{r ? [r.worst_abs_deviation_pct != null && `${num(r.worst_abs_deviation_pct, 2)} %`, r.worst_abs_deviation_K != null && `${num(r.worst_abs_deviation_K, 2)} K`].filter(Boolean).join(' / ') || '—' : ''}</td>
                    <td className="row-actions">
                      <button className="btn-sm" onClick={() => run([c.id])} disabled={!!job}>Run</button>
                      {r && <button className="btn-sm" onClick={() => setOpen(r)}>Details</button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {hist.length > 0 && (
        <Collapsible title={`Your previous runs in this browser (${hist.length})`}>
          {hist.map((h) => <div key={h.at} className="small">{timeAgo(h.at)} · {Object.values(h.statuses).filter((s) => s === 'PASS').length}/{Object.keys(h.statuses).length} PASS · {h.engine}</div>)}
        </Collapsible>
      )}
      <p className="small muted mt-16">Engine {data?.engine_version} · original program SHA-256 {data?.original_sha256?.slice(0, 16)}… Headline rows are what each routine presents as its result (ratings, temperatures, withstand); intermediate rows (T1–T4, λ, R…) are judged and shown separately.</p>
      {open && (
        <Modal title={open.title} onClose={() => setOpen(null)} wide>
          <p className="small">{open.note}</p>
          <p className="small muted">Tolerance: {open.tolerance_source}. {open.verification}.</p>
          {['headline', 'intermediate'].map((kind) => {
            const rs = open.rows.filter((x) => x.kind === kind)
            return rs.length > 0 && (
              <div key={kind} className="mt-16">
                <h4 style={{ margin: '0 0 8px' }}>{kind === 'headline' ? 'Headline comparisons' : 'Intermediate quantities'}</h4>
                <div className="table-scroll"><table className="data-table">
                  <thead><tr><th>Quantity</th><th className="num">Calculated</th><th className="num">Reference</th><th className="num">Deviation</th><th>Tolerance</th><th>Within</th></tr></thead>
                  <tbody>{rs.map((x, k) => (
                    <tr key={k} className={x.within === false ? 'row-fail' : ''}>
                      <td style={{ whiteSpace: 'normal' }}>{x.label}</td><td className="num">{x.computed ?? '—'}</td><td className="num">{x.reference ?? '—'}</td>
                      <td className="num">{x.deviation != null ? `${num(x.deviation, 2)} ${x.unit === '%' ? '%' : x.unit}` : '—'}</td>
                      <td>{x.tolerance ?? (x.flag ? 'routine flag' : '—')}</td>
                      <td>{x.within == null ? '—' : <StatusBadge status={x.within ? 'PASS' : 'FAIL'} label={x.within ? 'yes' : 'no'} />}</td>
                    </tr>))}</tbody>
                </table></div>
              </div>
            )
          })}
          <Collapsible title="Raw output of the original routine"><pre className="mono small" style={{ whiteSpace: 'pre-wrap' }}>{open.output}</pre></Collapsible>
        </Modal>
      )}
    </WithRail>
  )
}
