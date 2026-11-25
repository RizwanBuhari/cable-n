import { useMemo, useState } from 'react'
import { FeederDiagram } from '../diagrams/Diagrams'
import { num } from '../lib/format'
import { KV, Modal, Notice, StatTile, StatusBadge } from '../components/ui'
import { DataTable, Warnings } from './common'

export default function BatchResult({ inputs, result: r }) {
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(null)
  const rows = useMemo(() => {
    const all = [...r.rows, ...r.invalid_rows.map((x) => ({ ...x, status: 'invalid', invalid: true }))]
    return all.filter((x) => (filter === 'all' || x.status === filter) && (!q || `${x.tag} ${x.name || ''}`.toLowerCase().includes(q.toLowerCase())))
  }, [r, filter, q])
  const sm = r.summary
  const c = inputs.common
  return (
    <div className="section-gap">
      <div className="stat-grid" style={{ marginBottom: 0 }}>
        <StatTile label="Feeders entered" value={sm.total} tone="neutral" />
        <StatTile label="Calculated" value={sm.calculated} tone="good" />
        <StatTile label="Invalid rows" value={sm.invalid} tone={sm.invalid ? 'warn' : 'neutral'} hint="not calculated — see remarks" />
        <StatTile label="No solution" value={sm.no_solution} tone={sm.no_solution ? 'alert' : 'neutral'} />
        <StatTile label="SC check fails" value={sm.sc_fail} tone={sm.sc_fail ? 'alert' : 'neutral'} />
        <StatTile label="Parallel-run fallback" value={sm.parallel_fallback} tone="info" />
      </div>
      <KV rows={[['Construction', r.construction], ['Arrangement', r.installation_description], ['Rating table', r.table_key]]} />
      <div className="filter-bar">
        <div className="search-field"><input placeholder="Search feeder tag or name" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All statuses</option><option value="ok">OK</option><option value="sc_fail">SC fail</option>
          <option value="no_solution">No solution</option><option value="invalid">Invalid input</option>
        </select>
      </div>
      <DataTable rows={rows} rowKey={(x) => `${x.tag}-${x.index}`} onRow={(x) => setOpen(x)}
        rowClass={(x) => (x.status === 'ok' ? '' : 'row-fail')} columns={[
          { key: 'tag', label: 'Feeder' },
          { key: 'name', label: 'Name', render: (x) => x.name || '' },
          { key: 'ib', label: 'Ib A', num: true, render: (x) => (x.invalid ? '—' : num(x.ib, 1)) },
          { key: 'size', label: 'Size', sortValue: (x) => Number(x.rec?.size || 0), render: (x) => (x.rec ? `${x.rec.size} mm²` : '—') },
          { key: 'runs', label: 'Runs', num: true, sortValue: (x) => x.rec?.runs || 0, render: (x) => x.rec?.runs ?? '—' },
          { key: 'circuit', label: 'Configuration', render: (x) => x.circuit || '—' },
          { key: 'vd', label: 'VD %', num: true, sortValue: (x) => x.rec?.voltage_drop ?? -1, render: (x) => (x.rec ? num(x.rec.voltage_drop, 2) : '—') },
          { key: 'iz', label: 'Iz A', num: true, sortValue: (x) => x.rec?.derated_current ?? -1, render: (x) => (x.rec ? num(x.rec.derated_current, 1) : '—') },
          { key: 'util', label: 'Util %', num: true, sortValue: (x) => x.rec?.utilisation ?? -1, render: (x) => (x.rec ? num(x.rec.utilisation, 0) : '—') },
          { key: 'sc', label: 'SC', sortValue: (x) => x.rec?.sc_status || '', render: (x) => (x.rec ? <StatusBadge status={x.rec.sc_status || 'NOT_CHECKED'} /> : '—') },
          { key: 'status', label: 'Status', render: (x) => <StatusBadge status={x.status} /> },
          { key: 'remarks', label: 'Remarks', sortable: false, render: (x) => <span className="small">{x.invalid ? x.errors.join('; ') : [x.multi_fallback && 'Parallel-run fallback', x.governing && `Governs: ${x.governing}`].filter(Boolean).join(' · ')}</span> },
        ]} />
      <Warnings warnings={r.warnings} />
      {open && (
        <Modal title={`Feeder ${open.tag}${open.name ? ` — ${open.name}` : ''}`} onClose={() => setOpen(null)} wide>
          {open.invalid ? <Notice tone="alert">Not calculated: {open.errors.join('; ')}</Notice> : (
            <div className="section-gap">
              {!open.rec && <Notice tone="alert">No configuration in the rated range meets all criteria.</Notice>}
              {open.rec && (
                <>
                  <KV rows={[['Design current', `${num(open.ib, 2)} A`], ['Selected', open.circuit], ['Derating chain', open.chain],
                    ['Governing constraint', open.governing], ['Excluded smaller sizes', open.exclusions || '—'],
                    ['Voltage drop', `${num(open.rec.voltage_drop, 3)} %`],
                    ['Short-circuit', `${num(open.rec.short_circuit, 2)} kA${open.rec.sc_status ? ` vs ${num(open.rec.sc_required, 2)} kA → ${open.rec.sc_status}` : ''}`]]} />
                  <FeederDiagram installation={c.installation} arrangement={r.arrangement} coreType={c.core_type} runs={open.rec.runs}
                    spacing={open.rec.spacing} depth={c.depth} material={c.material} label={open.circuit} />
                </>
              )}
              {open.candidates?.length > 0 && (
                <>
                  <h4>Single-run sizes that pass</h4>
                  <DataTable rows={open.candidates} rowKey={(x) => x.size} columns={[
                    { key: 'size', label: 'Size mm²' }, { key: 'derated_current', label: 'Iz A', num: true, render: (x) => num(x.derated_current, 1) },
                    { key: 'utilisation', label: 'Util %', num: true, render: (x) => num(x.utilisation, 0) },
                    { key: 'voltage_drop', label: 'VD %', num: true, render: (x) => num(x.voltage_drop, 2) },
                    { key: 'sc_status', label: 'SC', render: (x) => <StatusBadge status={x.sc_status || 'NOT_CHECKED'} /> }]} />
                </>
              )}
              {open.spacing_variants?.length > 0 && (
                <>
                  <h4>Parallel-run variants by spacing</h4>
                  <DataTable rows={open.spacing_variants} rowKey={(x) => `${x.spacing}-${x.size}-${x.runs}`} columns={[
                    { key: 'spacing', label: 'Spacing' }, { key: 'size', label: 'Size mm²' }, { key: 'runs', label: 'Runs', num: true },
                    { key: 'derated_current', label: 'Iz A', num: true, render: (x) => num(x.derated_current, 1) },
                    { key: 'voltage_drop', label: 'VD %', num: true, render: (x) => num(x.voltage_drop, 2) },
                    { key: 'sc_status', label: 'SC', render: (x) => <StatusBadge status={x.sc_status || 'NOT_CHECKED'} /> }]} />
                </>
              )}
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}
