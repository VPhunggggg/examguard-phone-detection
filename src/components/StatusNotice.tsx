import { AlertTriangle, CheckCircle2, Info, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

export type NoticeTone = 'error' | 'success' | 'info' | 'loading'

type StatusNoticeProps = {
  tone?: NoticeTone
  children: ReactNode
}

const icons = {
  error: AlertTriangle,
  success: CheckCircle2,
  info: Info,
  loading: LoaderCircle,
}

function StatusNotice({ tone = 'info', children }: StatusNoticeProps) {
  const Icon = icons[tone]

  return (
    <div
      className="tool-notice"
      data-tone={tone === 'loading' ? 'info' : tone}
      role={tone === 'error' ? 'alert' : 'status'}
      aria-live={tone === 'error' ? 'assertive' : 'polite'}
    >
      <Icon
        className={tone === 'loading' ? 'tool-spin-icon' : undefined}
        size={16}
        aria-hidden="true"
      />
      <span>{children}</span>
    </div>
  )
}

export default StatusNotice
