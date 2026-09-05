import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  FileWarning,
  ShieldAlert,
  Slash,
} from 'lucide-react'
import type { AuditVerdict } from '../types'

export const verdictMeta: Record<AuditVerdict, { label: string; icon: typeof CheckCircle2 }> = {
  verified: { label: 'Verified', icon: CheckCircle2 },
  context_review: { label: 'Context review', icon: AlertTriangle },
  unsupported: { label: 'Unsupported', icon: FileWarning },
  likely_fabricated: { label: 'Likely fabricated', icon: ShieldAlert },
  unverified: { label: 'Unverified', icon: CircleHelp },
  out_of_scope: { label: 'Out of scope', icon: Slash },
}

export function VerdictBadge({ verdict }: { verdict: AuditVerdict }) {
  const { label, icon: Icon } = verdictMeta[verdict]
  return (
    <span className={`verdict verdict-${verdict}`}>
      <Icon size={14} aria-hidden="true" />
      {label}
    </span>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {action && <div className="header-action">{action}</div>}
    </header>
  )
}

export function LoadingPanel({ label = 'Loading' }: { label?: string }) {
  return <div className="panel loading-panel"><span className="spinner" />{label}…</div>
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="panel error-panel" role="alert">
      <AlertTriangle size={18} />
      <div><strong>Something needs attention</strong><p>{message}</p></div>
    </div>
  )
}
