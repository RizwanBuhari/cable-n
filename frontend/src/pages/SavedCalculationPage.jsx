import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Icon } from '../components/icons'
import { OutputBar } from '../components/Outputs'
import { Collapsible, EmptyState, KV, PageHeader, PageLoader, VerificationNotice } from '../components/ui'
import { MODE_LABEL, MODE_PATH, dateTime, stableKey } from '../lib/format'
import { db } from '../lib/store'
import AdvancedResult from '../results/AdvancedResult'
import BatchResult from '../results/BatchResult'
import { RunInfo } from '../results/common'
import SingleFeederResult from '../results/SingleFeederResult'
import CurrentRatingView from '../results/CurrentRatingView'

export function ResultView({ mode, inputs, result }) {
  if (mode === 'single_feeder') return <SingleFeederResult inputs={inputs} result={result} />
  if (mode === 'batch') return <BatchResult inputs={inputs} result={result} />
  if (mode === 'current_rating') return <CurrentRatingView inputs={inputs} result={result} />
  return <AdvancedResult inputs={inputs} result={result} />
}

export default function SavedCalculationPage() {
  const { id } = useParams()
  const [rec, setRec] = useState(undefined)
  useEffect(() => { db.get('calculations', id).then((r) => setRec(r || null)) }, [id])
  if (rec === undefined) return <PageLoader />
  if (!rec) return <EmptyState>Saved calculation not found in this browser. <Link className="table-link" to="/calculators?tab=saved">Back to saved work</Link></EmptyState>
  const run = rec.result ? { result: rec.result, summary: rec.summary, engine_version: rec.engineVersion, inputsKey: stableKey(rec.inputs), stored: true } : null
  return (
    <div>
      <PageHeader icon={Icon.save} title={rec.title} hint={`${MODE_LABEL[rec.mode]} · ${rec.scenario} · revision ${rec.revision || 1} · saved ${dateTime(rec.updatedAt)}`}
        actions={<Link className="btn-primary" to={`${MODE_PATH[rec.mode]}?load=${rec.id}`}>{Icon.edit} Open in calculator</Link>} />
      {rec.history?.length > 0 && (
        <Collapsible title={`Revision history (${rec.history.length} earlier)`}>
          {rec.history.slice().reverse().map((h) => (
            <KV key={h.revision} rows={[[`Revision ${h.revision}`, `${dateTime(h.at)}${h.note ? ` — ${h.note}` : ''}`], ['Outcome', h.summary ? `${h.summary.outcome || ''} ${h.summary.cable_size || ''}` : 'draft']]} />
          ))}
          <p className="small muted">Earlier inputs are kept with the record (Export JSON includes them).</p>
        </Collapsible>
      )}
      {run ? (
        <div className="mt-16">
          <RunInfo run={run} />
          <ResultView mode={rec.mode} inputs={rec.inputs} result={rec.result} />
          <div className="mt-16"><VerificationNotice /></div>
          <div className="sticky-actions"><OutputBar mode={rec.mode} inputs={rec.inputs} run={run} saved={rec} onSaved={setRec} title={rec.title} /></div>
        </div>
      ) : <EmptyState>This saved item has no result yet — open it in the calculator to run it.</EmptyState>}
    </div>
  )
}
