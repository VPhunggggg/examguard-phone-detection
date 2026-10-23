import type { ReactNode } from 'react'

type MediaPanelProps = {
  title: string
  meta?: string
  children: ReactNode
}

function MediaPanel({ title, meta, children }: MediaPanelProps) {
  return (
    <article className="tool-panel">
      <header className="tool-panel-header">
        <div>
          <h3 className="tool-panel-label">{title}</h3>
          {meta ? <p className="tool-panel-meta">{meta}</p> : null}
        </div>
      </header>
      <div className="tool-media-frame">{children}</div>
    </article>
  )
}

export default MediaPanel
