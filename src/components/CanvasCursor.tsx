import useCanvasCursor from '../hooks/use-canvasCursor'

function CanvasCursor() {
  useCanvasCursor()

  return (
    <canvas
      id="canvas"
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[var(--z-cursor)] h-full w-full"
    />
  )
}

export default CanvasCursor
