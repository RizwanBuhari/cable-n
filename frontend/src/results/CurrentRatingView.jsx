import { BankDiagram } from '../diagrams/Diagrams'
import { num } from '../lib/format'
import { StatTile, StatusBadge } from '../components/ui'
import { DataTable, Warnings } from './common'

/** Read-only view of a Mode 3 result (used for saved calculations). */
export default function CurrentRatingView({ inputs, result: r }) {
  return (
    <div className="section-gap">
      <div className="stat-grid">
        <StatTile label="Positions rated" value={r.summary.positions} tone="neutral" />
        <StatTile label="Overloaded" value={r.summary.overload} tone={r.summary.overload ? 'alert' : 'good'} />
        <StatTile label="Lowest rating" value={`${num(r.summary.min_rating, 0)} A`} tone="brand" />
      </div>
      <BankDiagram banks={inputs.banks.map((b) => ({ v_pitch: 0, ...b }))} gaps={inputs.gaps || []} positions={r.positions} installation={inputs.installation} />
      <DataTable rows={r.positions} rowKey={(p) => p.pos} rowClass={(p) => (p.status === 'OVERLOAD' ? 'row-fail' : '')} columns={[
        { key: 'pos', label: 'Position' }, { key: 'config_label', label: 'Cable' }, { key: 'base', label: 'Base A', num: true },
        { key: 'ambient', label: 'Ca', num: true, render: (p) => num(p.ambient, 3) }, { key: 'soil', label: 'Cs', num: true, render: (p) => num(p.soil, 2) },
        { key: 'depth_f', label: 'Cd', num: true, render: (p) => num(p.depth_f, 2) }, { key: 'cg', label: 'Cg', num: true, render: (p) => num(p.cg, 2) },
        { key: 'inter', label: 'Cint', num: true, render: (p) => num(p.inter, 2) }, { key: 'iz', label: 'Rating A', num: true, render: (p) => num(p.iz, 1) },
        { key: 'util', label: 'Util %', num: true, render: (p) => (p.util == null ? '—' : num(p.util, 0)) },
        { key: 'status', label: 'Status', render: (p) => (p.status ? <StatusBadge status={p.status} /> : '—') }]} />
      <Warnings warnings={r.warnings} />
    </div>
  )
}
