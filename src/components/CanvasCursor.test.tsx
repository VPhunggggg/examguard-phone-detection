import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CanvasCursor from './CanvasCursor'

type ContextMock = Pick<
  CanvasRenderingContext2D,
  | 'beginPath'
  | 'clearRect'
  | 'closePath'
  | 'moveTo'
  | 'quadraticCurveTo'
  | 'stroke'
> & {
  canvas: HTMLCanvasElement
  frame: number
  running: boolean
  globalCompositeOperation: GlobalCompositeOperation
  lineWidth: number
  strokeStyle: string | CanvasGradient | CanvasPattern
}

let context: ContextMock
let frameCallbacks: FrameRequestCallback[]
let requestFrame: ReturnType<typeof vi.fn>

function dispatchMouseMove(clientX = 240, clientY = 180) {
  const event = new MouseEvent('mousemove', {
    bubbles: true,
    cancelable: true,
    clientX,
    clientY,
  })
  act(() => document.dispatchEvent(event))
  return event
}

function dispatchTouchMove(pageX = 320, pageY = 240) {
  const event = new Event('touchmove', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'touches', {
    value: [{ pageX, pageY }],
  })
  act(() => document.dispatchEvent(event))
  return event
}

function runNextFrame() {
  const callback = frameCallbacks.shift()
  if (!callback) throw new Error('No animation frame was scheduled')
  act(() => callback(16))
}

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    writable: true,
    value: 800,
  })
  Object.defineProperty(window, 'innerHeight', {
    configurable: true,
    writable: true,
    value: 600,
  })

  frameCallbacks = []
  requestFrame = vi.fn((callback: FrameRequestCallback) => {
    frameCallbacks.push(callback)
    return frameCallbacks.length
  })
  vi.stubGlobal('requestAnimationFrame', requestFrame)

  context = {
    beginPath: vi.fn(),
    clearRect: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    quadraticCurveTo: vi.fn(),
    stroke: vi.fn(),
    canvas: document.createElement('canvas'),
    frame: 0,
    running: false,
    globalCompositeOperation: 'source-over',
    lineWidth: 0,
    strokeStyle: '',
  }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => {
    const canvas = document.querySelector<HTMLCanvasElement>('canvas#canvas')
    if (canvas) context.canvas = canvas
    return context as unknown as CanvasRenderingContext2D
  })
})

afterEach(() => {
  cleanup()
  frameCallbacks = []
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('CanvasCursor', () => {
  it('renders the inert full-screen canvas at the cursor layer', () => {
    const { container } = render(<CanvasCursor />)
    const canvas = container.querySelector('canvas#canvas')

    expect(canvas).toHaveAttribute('aria-hidden', 'true')
    expect(canvas).toHaveClass(
      'pointer-events-none',
      'fixed',
      'inset-0',
      'z-[var(--z-cursor)]',
      'h-full',
      'w-full',
    )
    expect(HTMLCanvasElement.prototype.getContext).toHaveBeenCalledWith('2d')
    expect(canvas).toHaveAttribute('width', '780')
    expect(canvas).toHaveAttribute('height', '600')
    expect(requestFrame).not.toHaveBeenCalled()
  })

  it('resizes the drawing surface using the supplied viewport calculation', () => {
    const { container } = render(<CanvasCursor />)
    const canvas = container.querySelector('canvas#canvas') as HTMLCanvasElement

    window.innerWidth = 1024
    window.innerHeight = 768
    act(() => window.dispatchEvent(new Event('resize')))

    expect(canvas.width).toBe(1004)
    expect(canvas.height).toBe(768)
  })

  it('stops the supplied render flag and removes its named listeners on unmount', () => {
    const removeDocumentListener = vi.spyOn(document, 'removeEventListener')
    const removeBodyListener = vi.spyOn(document.body, 'removeEventListener')
    const removeWindowListener = vi.spyOn(window, 'removeEventListener')
    const { unmount } = render(<CanvasCursor />)

    unmount()

    expect(context.running).toBe(false)
    expect(removeDocumentListener.mock.calls.some(([type]) => type === 'mousemove')).toBe(true)
    expect(removeDocumentListener.mock.calls.some(([type]) => type === 'touchstart')).toBe(true)
    expect(removeBodyListener.mock.calls.some(([type]) => type === 'orientationchange')).toBe(true)
    expect(removeWindowListener.mock.calls.some(([type]) => type === 'resize')).toBe(true)
  })

  it('draws the original 20-by-50 purple trails and tracks mouse and touch movement', () => {
    render(<CanvasCursor />)

    const mouseEvent = dispatchMouseMove()

    expect(mouseEvent.defaultPrevented).toBe(true)
    expect(context.running).toBe(true)
    expect(context.frame).toBe(2)
    expect(context.globalCompositeOperation).toBe('lighter')
    expect(context.lineWidth).toBe(1)
    expect(context.strokeStyle).toMatch(/^hsla\(\d+,50%,50%,0\.2\)$/)
    expect(context.clearRect).toHaveBeenCalledWith(0, 0, 780, 600)
    expect(context.beginPath).toHaveBeenCalledTimes(20)
    expect(context.stroke).toHaveBeenCalledTimes(20)
    expect(context.closePath).toHaveBeenCalledTimes(20)
    expect(context.quadraticCurveTo).toHaveBeenCalledTimes(20 * (50 - 2))
    expect(requestFrame).toHaveBeenCalledTimes(1)
    expect(frameCallbacks).toHaveLength(1)

    const touchEvent = dispatchTouchMove()
    expect(touchEvent.defaultPrevented).toBe(true)

    runNextFrame()
    expect(context.frame).toBe(3)
    expect(context.stroke).toHaveBeenCalledTimes(40)
    expect(frameCallbacks).toHaveLength(1)
  })
})
