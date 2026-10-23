import type { ReactNode } from 'react'

export type ToolBackgroundVariant = 'image' | 'video' | 'camera'
export type ToolStatusTone = 'olive' | 'cyan' | 'coral'

type ToolPageLayoutProps = {
  kicker: string
  title: string
  description: string
  status: string
  statusTone: ToolStatusTone
  background: {
    src: string
    variant: ToolBackgroundVariant
  }
  workspace: ReactNode
  settings: ReactNode
  children?: ReactNode
  busy?: boolean
  onSubmit?: () => void
}

function ToolPageLayout({
  kicker,
  title,
  description,
  status,
  statusTone,
  background,
  workspace,
  settings,
  children,
  busy = false,
  onSubmit,
}: ToolPageLayoutProps) {
  return (
    <main className="tool-page" data-background={background.variant}>
      <div className="tool-page-background" data-variant={background.variant} aria-hidden="true">
        <img
          className="tool-page-background-image"
          src={background.src}
          alt=""
          aria-hidden="true"
          decoding="async"
          draggable={false}
        />
      </div>

      <div className="tool-shell">
        <header className="tool-heading">
          <div className="tool-heading-topline">
            <p className="tool-kicker">{kicker}</p>
            <span
              className="tool-status-chip"
              data-tone={statusTone}
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              {status}
            </span>
          </div>

          <div className="tool-heading-copy">
            <h1 className="tool-title">{title}</h1>
            <p className="tool-description">{description}</p>
          </div>
        </header>

        <section className="tool-operation-deck" aria-label="Bàn điều khiển phân tích">
          <form
            className="tool-grid tool-operation-grid"
            aria-busy={busy}
            onSubmit={(event) => {
              event.preventDefault()
              onSubmit?.()
            }}
          >
            <section className="tool-stack tool-operation-workspace" aria-label="Khu vực xử lý">
              {workspace}
            </section>
            <aside className="tool-settings-column tool-operation-settings" aria-label="Thiết lập công cụ">
              {settings}
            </aside>
          </form>
        </section>

        {children}
      </div>
    </main>
  )
}

export default ToolPageLayout
