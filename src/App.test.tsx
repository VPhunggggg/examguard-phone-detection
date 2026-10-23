import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'

vi.mock('./components/CanvasCursor', () => ({
  default: () => null,
}))

import App from './App'

const TEST_CONFIG = {
  ok: true as const,
  model_options: [
    {
      value: 'yolo11n_behavior_p2',
      label: 'Phone + Using Phone',
      available: true,
      warning: '',
    },
    {
      value: 'yolov8n_coco_phone',
      label: 'Phone',
      available: true,
      warning: '',
    },
  ],
  defaults: {
    model_mode: 'yolo11n_behavior_p2',
    conf_threshold: 0.55,
  },
  confidence: {
    min: 0.1,
    max: 0.9,
    step: 0.05,
  },
  upload: {
    max_bytes: 10_000_000,
    max_mb: 10,
    image: {
      extensions: ['.jpg', '.jpeg', '.png'],
      mime_types: ['image/jpeg', 'image/png'],
    },
    video: {
      extensions: ['.mp4'],
      mime_types: ['video/mp4'],
    },
  },
}

const IMAGE_RESULT = {
  ok: true as const,
  original_url: '/media/uploads/exam.jpg',
  output_url: '/media/outputs/exam-detected.jpg',
  detections: [
    {
      label: 'phone',
      confidence: 0.92,
      class_id: 1,
      is_phone: true,
      x1: 12,
      y1: 18,
      x2: 98,
      y2: 164,
    },
    {
      label: 'using_phone',
      confidence: 0.87,
      class_id: 7,
      is_phone: true,
      x1: 20,
      y1: 24,
      x2: 110,
      y2: 180,
    },
    {
      label: 'using_phone',
      confidence: 0.81,
      class_id: 7,
      is_phone: true,
      x1: 140,
      y1: 34,
      x2: 226,
      y2: 188,
    },
  ],
  settings: {
    model_mode: 'yolo11n_behavior_p2',
    conf_threshold: 0.55,
  },
  message: 'Phân tích ảnh hoàn tất.',
}

const VIDEO_RESULT = {
  ok: true as const,
  input_url: '/media/uploads/exam.mp4',
  output_url: '/media/outputs/exam-detected.mp4',
  settings: {
    model_mode: 'yolo11n_behavior_p2',
    conf_threshold: 0.55,
  },
  message: 'Xử lý video hoàn tất.',
}

type Responder = () => Promise<Response>
type CameraResponder = (request?: RequestInit) => Promise<Response>

let fetchMock: ReturnType<typeof vi.fn>
let imageResponder: Responder
let videoResponder: Responder
let cameraResponder: CameraResponder
let cameraConnectionSequence: number
let cameraConnectionSources: Map<string, string>
let createObjectUrlMock: ReturnType<typeof vi.fn>
let revokeObjectUrlMock: ReturnType<typeof vi.fn>

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function cameraResultFromRequest(request?: RequestInit) {
  const body = JSON.parse(String(request?.body ?? '{}')) as {
    source_type: 'webcam' | 'phone'
    camera_index?: number
    camera_url?: string
    model_mode: string
    conf_threshold: number
    current_connection_id?: string
  }
  const phoneUrl = new URL(body.camera_url ?? 'http://192.168.1.20:8080/video')
  if (phoneUrl.pathname === '/' || phoneUrl.pathname === '') phoneUrl.pathname = '/video'
  const source = body.source_type === 'phone'
    ? { source_type: 'phone' as const, camera_url: phoneUrl.toString() }
    : { source_type: 'webcam' as const, camera_index: body.camera_index ?? 0 }
  const sourceLabel = source.source_type === 'phone'
    ? `Điện thoại · ${new URL(source.camera_url).hostname}`
    : `Webcam · Camera ${source.camera_index}`
  const sourceKey = JSON.stringify(source)
  const reusableConnectionId = body.current_connection_id
    && cameraConnectionSources.get(body.current_connection_id) === sourceKey
    ? body.current_connection_id
    : null
  const connectionId = reusableConnectionId ?? `camera-connection-${++cameraConnectionSequence}`
  cameraConnectionSources.set(connectionId, sourceKey)
  const feedParams = new URLSearchParams({
    connection_id: connectionId,
    model_mode: body.model_mode,
    conf_threshold: String(body.conf_threshold),
  })

  return {
    ok: true as const,
    connection_id: connectionId,
    feed_url: `/video_feed?${feedParams.toString()}`,
    source_label: sourceLabel,
    source,
    settings: {
      model_mode: body.model_mode,
      conf_threshold: body.conf_threshold,
    },
  }
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location-search">{location.search}</output>
}

function renderRoute(route: string, withLocation = false) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
      {withLocation ? <LocationProbe /> : null}
    </MemoryRouter>,
  )
}

function findRequest(path: string): [RequestInfo | URL, RequestInit | undefined] {
  const call = fetchMock.mock.calls.find(([input]) => String(input) === path)
  if (!call) throw new Error(`Không tìm thấy request ${path}`)
  return call as [RequestInfo | URL, RequestInit | undefined]
}

beforeEach(() => {
  cameraConnectionSequence = 0
  cameraConnectionSources = new Map()
  imageResponder = () => Promise.resolve(jsonResponse(IMAGE_RESULT))
  videoResponder = () => Promise.resolve(jsonResponse(VIDEO_RESULT))
  cameraResponder = (request) => Promise.resolve(jsonResponse(cameraResultFromRequest(request)))

  fetchMock = vi.fn((input: RequestInfo | URL, request?: RequestInit) => {
    const url = String(input)
    if (url === '/api/config') return Promise.resolve(jsonResponse(TEST_CONFIG))
    if (url === '/api/image') return imageResponder()
    if (url === '/api/video') return videoResponder()
    if (url === '/api/camera/connect') return cameraResponder(request)
    if (url.startsWith('/api/camera/connections/') && request?.method === 'DELETE') {
      return Promise.resolve(jsonResponse({ ok: true, released: true }))
    }
    return Promise.reject(new Error(`Unexpected fetch: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('IntersectionObserver', class {
    readonly root = null
    readonly rootMargin = ''
    readonly thresholds: number[] = []

    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] { return [] }
  })

  createObjectUrlMock = vi.fn(() => 'blob:test-preview')
  revokeObjectUrlMock = vi.fn()
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    writable: true,
    value: createObjectUrlMock,
  })
  Object.defineProperty(URL, 'revokeObjectURL', {
    configurable: true,
    writable: true,
    value: revokeObjectUrlMock,
  })
  Object.defineProperty(window, 'scrollTo', {
    configurable: true,
    writable: true,
    value: vi.fn(),
  })
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    writable: true,
    value: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('SPA routing', () => {
  it.each([
    ['/', 'Giám sát thi cử bằng AI'],
    ['/image', 'Phân tích ảnh thi cử'],
    ['/video', 'Phân tích video kỳ thi'],
    ['/camera', 'Giám sát camera trực tiếp'],
    ['/khong-ton-tai', 'Không tìm thấy trang'],
  ])('renders %s at the expected page heading', async (route, heading) => {
    renderRoute(route)

    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })

  it('renders the landing shell without legacy English interface copy', async () => {
    renderRoute('/')

    await screen.findByRole('heading', { level: 1, name: 'Giám sát thi cử bằng AI' })
    const pageText = document.body.textContent ?? ''
    const aboutHeading = screen.getByRole('heading', {
      level: 2,
      name: 'Được xây dựng cho kỳ thi công bằng hơn, giám sát thông minh hơn và rà soát bằng chứng nhanh hơn.',
    })

    expect(pageText).toContain('Trang chủ')
    expect(pageText).toContain('Giám sát thi cử AI')
    expect(pageText).toContain('Công bằng × An toàn')
    expect(aboutHeading).toHaveAttribute('data-scroll-reveal', 'phrases')
    expect(aboutHeading.querySelectorAll('[data-reveal-phrase="true"]')).toHaveLength(6)
    for (const legacyCopy of ['Home', 'Phone Detected', 'Monitoring Active', 'Evidence Saved', 'Fairness × Security']) {
      expect(pageText).not.toContain(legacyCopy)
    }
  })

  it('opens the Telegram alert bot safely and removes the trial email form', async () => {
    renderRoute('/')

    await screen.findByRole('heading', { level: 1, name: 'Giám sát thi cử bằng AI' })
    const telegramLink = screen.getByRole('link', { name: 'Nhận thông báo gian lận qua Telegram' })

    expect(telegramLink).toHaveAttribute('href', 'https://t.me/ai_exam_monitoring_2026_bot')
    expect(telegramLink).toHaveAttribute('target', '_blank')
    expect(telegramLink).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByText('Mở bot và nhấn Bắt đầu để đăng ký nhận cảnh báo.')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Email nhận bản dùng thử' })).not.toBeInTheDocument()
  })

  it.each([
    { route: '/image', variant: 'image', filename: 'tool-image-exam-desk-v1.webp', accessibleImages: 0 },
    { route: '/video', variant: 'video', filename: 'tool-video-exam-review-v1.webp', accessibleImages: 0 },
    { route: '/camera', variant: 'camera', filename: 'tool-camera-live-room-v1.webp', accessibleImages: 1 },
  ])('uses one route-specific decorative background on $route', async ({ route, variant, filename, accessibleImages }) => {
    renderRoute(route)

    await screen.findByRole('heading', { level: 1 })
    const page = document.querySelector(`.tool-page[data-background="${variant}"]`)
    const background = page?.querySelector<HTMLImageElement>('.tool-page-background-image')

    expect(page).toBeInTheDocument()
    expect(background).toHaveAttribute('src', expect.stringContaining(filename))
    expect(background).toHaveAttribute('alt', '')
    expect(background).toHaveAttribute('aria-hidden', 'true')
    expect(document.querySelectorAll('.tool-page-background-image')).toHaveLength(1)
    await waitFor(() => expect(screen.queryAllByRole('img')).toHaveLength(accessibleImages))
  })
})

describe('image analysis', () => {
  it('loads config, submits the expected FormData fields, and renders evidence', async () => {
    const user = userEvent.setup()
    const view = renderRoute('/image')
    const file = new File(['image-bytes'], 'phong-thi.jpg', { type: 'image/jpeg' })

    await user.upload(await screen.findByLabelText('Chọn ảnh để phân tích'), file)
    expect(createObjectUrlMock).toHaveBeenCalledWith(file)

    const submit = await screen.findByRole('button', { name: 'Bắt đầu phân tích' })
    await waitFor(() => expect(submit).toBeEnabled())
    await user.click(submit)

    expect(await screen.findByRole('heading', { level: 2, name: 'Kết quả nhận diện' })).toBeInTheDocument()
    expect(screen.getByText('Phân tích ảnh hoàn tất.')).toBeInTheDocument()
    expect(screen.getAllByText('Đang sử dụng điện thoại')).toHaveLength(2)
    const class1Pills = screen.getAllByText('Phone · Class 1')
      .filter((item) => item.classList.contains('tool-pill'))
    const class7Pills = screen.getAllByText('Using Phone · Class 7')
      .filter((item) => item.classList.contains('tool-pill'))
    expect(class1Pills).toHaveLength(1)
    expect(class1Pills[0]).toHaveAttribute('data-alert', 'true')
    expect(class7Pills).toHaveLength(2)
    expect(class7Pills.every((item) => item.getAttribute('data-alert') === 'true')).toBe(true)
    const summary = screen.getByLabelText('Tóm tắt kết quả')
    expect(summary.querySelectorAll('.tool-summary-item')).toHaveLength(5)
    expect(Array.from(summary.querySelectorAll('.tool-summary-item')).map((item) => ({
      label: item.querySelector('dt')?.textContent,
      value: item.querySelector('dd')?.textContent,
    }))).toEqual(expect.arrayContaining([
      { label: 'Phone · Class 1', value: '1' },
      { label: 'Using Phone · Class 7', value: '2' },
    ]))
    expect(screen.getByRole('img', { name: 'Ảnh gốc được tải lên để phân tích' })).toHaveAttribute(
      'src',
      IMAGE_RESULT.original_url,
    )

    const [, request] = findRequest('/api/image')
    const body = request?.body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('image_file')).toBe(file)
    expect(body.get('model_mode')).toBe('yolo11n_behavior_p2')
    expect(body.get('conf_threshold')).toBe('0.55')

    view.unmount()
    expect(revokeObjectUrlMock).toHaveBeenCalledWith('blob:test-preview')
  })

  it('shows a structured server error without rendering stale results', async () => {
    imageResponder = () => Promise.resolve(jsonResponse({
      ok: false,
      error: { code: 'processing_failed', message: 'Không thể xử lý ảnh.' },
    }, 422))
    const user = userEvent.setup()
    renderRoute('/image')

    await user.upload(
      await screen.findByLabelText('Chọn ảnh để phân tích'),
      new File(['image-bytes'], 'loi.jpg', { type: 'image/jpeg' }),
    )
    const submit = await screen.findByRole('button', { name: 'Bắt đầu phân tích' })
    await waitFor(() => expect(submit).toBeEnabled())
    await user.click(submit)

    expect(await screen.findByRole('alert')).toHaveTextContent('Không thể xử lý ảnh.')
    expect(screen.queryByRole('heading', { name: 'Kết quả nhận diện' })).not.toBeInTheDocument()
  })

  it.each([
    {
      label: 'Phone + Using Phone',
      modelMode: 'yolo11n_behavior_p2',
      filename: 'behavior-p2.jpg',
    },
    {
      label: 'Phone',
      modelMode: 'yolov8n_coco_phone',
      filename: 'coco-phone.jpg',
    },
  ])('submits $label when selected', async ({ modelMode, filename }) => {
    const user = userEvent.setup()
    renderRoute('/image')
    const file = new File(['image-bytes'], filename, { type: 'image/jpeg' })

    await user.upload(await screen.findByLabelText('Chọn ảnh để phân tích'), file)
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Mô hình' }),
      modelMode,
    )
    await user.click(screen.getByRole('button', { name: 'Bắt đầu phân tích' }))

    await screen.findByRole('heading', { level: 2, name: 'Kết quả nhận diện' })
    const [, request] = findRequest('/api/image')
    const body = request?.body as FormData
    expect(body.get('model_mode')).toBe(modelMode)
  })
})

describe('video analysis', () => {
  it('keeps the form pending until synchronous processing completes, then shows both videos', async () => {
    let resolveVideo!: (response: Response) => void
    videoResponder = () => new Promise<Response>((resolve) => {
      resolveVideo = resolve
    })
    const user = userEvent.setup()
    renderRoute('/video')
    const file = new File(['video-bytes'], 'ky-thi.mp4', { type: 'video/mp4' })

    await user.upload(await screen.findByLabelText('Chọn video để phân tích'), file)
    const submit = await screen.findByRole('button', { name: 'Xử lý video' })
    await waitFor(() => expect(submit).toBeEnabled())
    await user.click(submit)

    expect(await screen.findByText('Đang xử lý video, vui lòng không đóng trang.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Đang xử lý…' })).toBeDisabled()

    const [, request] = findRequest('/api/video')
    const body = request?.body as FormData
    expect(body.get('video_file')).toBe(file)
    expect(body.get('model_mode')).toBe('yolo11n_behavior_p2')
    expect(body.get('conf_threshold')).toBe('0.55')

    resolveVideo(jsonResponse(VIDEO_RESULT))

    expect(await screen.findByRole('heading', { level: 2, name: 'Video đã xử lý' })).toBeInTheDocument()
    expect(screen.getByText('Xử lý video hoàn tất.')).toBeInTheDocument()
    const videos = document.querySelectorAll('.tool-media-grid video')
    expect(videos).toHaveLength(2)
    expect(videos[0]).toHaveAttribute('src', VIDEO_RESULT.input_url)
    expect(videos[1]).toHaveAttribute('src', VIDEO_RESULT.output_url)
  })

  it('reports video processing errors', async () => {
    videoResponder = () => Promise.resolve(jsonResponse({
      ok: false,
      error: { code: 'processing_failed', message: 'Video không thể giải mã.' },
    }, 422))
    const user = userEvent.setup()
    renderRoute('/video')

    await user.upload(
      await screen.findByLabelText('Chọn video để phân tích'),
      new File(['video-bytes'], 'loi.mp4', { type: 'video/mp4' }),
    )
    const submit = await screen.findByRole('button', { name: 'Xử lý video' })
    await waitFor(() => expect(submit).toBeEnabled())
    await user.click(submit)

    expect(await screen.findByRole('alert')).toHaveTextContent('Video không thể giải mã.')
    expect(screen.queryByRole('heading', { name: 'Video đã xử lý' })).not.toBeInTheDocument()
  })

  it.each([
    {
      label: 'Phone + Using Phone',
      modelMode: 'yolo11n_behavior_p2',
      filename: 'behavior-p2.mp4',
    },
    {
      label: 'Phone',
      modelMode: 'yolov8n_coco_phone',
      filename: 'coco-phone.mp4',
    },
  ])('submits and displays $label with its friendly name', async ({ label, modelMode, filename }) => {
    videoResponder = () => Promise.resolve(jsonResponse({
      ...VIDEO_RESULT,
      settings: {
        ...VIDEO_RESULT.settings,
        model_mode: modelMode,
      },
    }))
    const user = userEvent.setup()
    renderRoute('/video')
    const file = new File(['video-bytes'], filename, { type: 'video/mp4' })

    await user.upload(await screen.findByLabelText('Chọn video để phân tích'), file)
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Mô hình' }),
      modelMode,
    )
    await user.click(screen.getByRole('button', { name: 'Xử lý video' }))

    await screen.findByRole('heading', { level: 2, name: 'Video đã xử lý' })
    const [, request] = findRequest('/api/video')
    const body = request?.body as FormData
    expect(body.get('model_mode')).toBe(modelMode)
    expect(document.querySelector('.tool-summary-grid')).toHaveTextContent(`Mô hình${label}`)
  })
})

describe('camera monitoring', () => {
  it('auto-connects webcam 0 with defaults on a bare camera route', async () => {
    renderRoute('/camera', true)

    const stream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    const [, request] = findRequest('/api/camera/connect')
    expect(request?.method).toBe('POST')
    expect(request?.headers).toEqual(expect.objectContaining({
      Accept: 'application/json',
      'Content-Type': 'application/json',
    }))
    expect(JSON.parse(String(request?.body))).toEqual({
      source_type: 'webcam',
      camera_index: 0,
      model_mode: 'yolo11n_behavior_p2',
      conf_threshold: 0.55,
    })
    expect(stream).toHaveAttribute('src', expect.stringContaining('connection_id=camera-connection-1'))
    expect(stream.getAttribute('src')).not.toContain('camera_index')
    expect(screen.getByText('Đang chờ khung hình')).toBeInTheDocument()

    fireEvent.load(stream)
    expect(screen.getByText('AI đang xem xét')).toBeInTheDocument()
    expect(screen.getByText('Webcam · Camera 0')).toBeInTheDocument()
    expect(screen.getByTestId('location-search')).not.toHaveTextContent('source_type')
  })

  it('normalizes a legacy model query, reuses one session, and replaces the query after load', async () => {
    const user = userEvent.setup()
    renderRoute('/camera?model_mode=model_manh_nhat&conf_threshold=0.7', true)

    const stream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    expect(stream).toHaveAttribute('src', expect.stringContaining('model_mode=yolo11n_behavior_p2&conf_threshold=0.7'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('model_mode=yolo11n_behavior_p2')
    expect(screen.getByTestId('location-search')).toHaveTextContent('conf_threshold=0.7')

    fireEvent.load(stream)
    expect(screen.getAllByText('Đã nhận luồng hình').length).toBeGreaterThan(0)

    const confidence = screen.getByRole('slider', { name: 'Ngưỡng tin cậy' })
    fireEvent.change(confidence, { target: { value: '0.8' } })
    expect(screen.getByTestId('location-search')).toHaveTextContent('conf_threshold=0.7')

    await user.click(screen.getByRole('button', { name: 'Kiểm tra và kết nối' }))
    const connectRequests = fetchMock.mock.calls.filter(([input]) => String(input) === '/api/camera/connect')
    expect(JSON.parse(String(connectRequests[1]?.[1]?.body))).toEqual({
      source_type: 'webcam',
      camera_index: 0,
      model_mode: 'yolo11n_behavior_p2',
      conf_threshold: 0.8,
      current_connection_id: 'camera-connection-1',
    })

    const candidate = await screen.findByTestId('camera-candidate-stream')
    expect(candidate).toHaveAttribute('src', expect.stringContaining('connection_id=camera-connection-1'))
    expect(screen.queryByTestId('camera-active-stream')).not.toBeInTheDocument()
    expect(screen.getAllByRole('img', { name: 'Luồng camera giám sát kỳ thi' })).toHaveLength(1)
    expect(screen.getByText('Đang chờ khung hình')).toBeInTheDocument()
    expect(screen.getByTestId('location-search')).toHaveTextContent('conf_threshold=0.7')

    fireEvent.load(candidate)
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('conf_threshold=0.8'))

    const updatedStream = screen.getByTestId('camera-active-stream')
    expect(updatedStream).toHaveAttribute('src', expect.stringContaining('conf_threshold=0.8'))
    const beforeReconnect = updatedStream.getAttribute('src')

    fireEvent.error(updatedStream)
    expect(screen.getByText('AI đã tạm dừng')).toBeInTheDocument()
    const reconnect = await screen.findByRole('button', { name: 'Kết nối lại' })
    await user.click(reconnect)

    const reconnectCandidate = await screen.findByTestId('camera-candidate-stream')
    expect(screen.queryByTestId('camera-active-stream')).not.toBeInTheDocument()
    fireEvent.load(reconnectCandidate)
    const reconnectedStream = await screen.findByTestId('camera-active-stream')
    expect(reconnectedStream.getAttribute('src')).not.toBe(beforeReconnect)
    expect(screen.getByText('AI đang xem xét')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([input]) => String(input) === '/api/camera/connect')).toHaveLength(3)
  })

  it.each([
    { label: 'Phone + Using Phone', modelMode: 'yolo11n_behavior_p2' },
    { label: 'Phone', modelMode: 'yolov8n_coco_phone' },
  ])('reconnects the camera with $label when selected', async ({ modelMode }) => {
    const user = userEvent.setup()
    renderRoute('/camera', true)

    const initialStream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    fireEvent.load(initialStream)
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Mô hình' }),
      modelMode,
    )
    await user.click(screen.getByRole('button', { name: 'Kiểm tra và kết nối' }))

    const candidate = await screen.findByTestId('camera-candidate-stream')
    const connectRequests = fetchMock.mock.calls.filter(([input]) => String(input) === '/api/camera/connect')
    expect(JSON.parse(String(connectRequests[1]?.[1]?.body))).toEqual({
      source_type: 'webcam',
      camera_index: 0,
      model_mode: modelMode,
      conf_threshold: 0.55,
      current_connection_id: 'camera-connection-1',
    })
    expect(candidate).toHaveAttribute('src', expect.stringContaining(`model_mode=${modelMode}`))

    fireEvent.load(candidate)
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent(
      `model_mode=${modelMode}`,
    ))
  })

  it('accepts the IP Webcam base address, exposes pending state, and activates an opaque feed', async () => {
    const user = userEvent.setup()
    renderRoute('/camera', true)

    const initialStream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    fireEvent.load(initialStream)
    await user.click(screen.getByRole('radio', { name: /Camera điện thoại/ }))

    const connectButton = screen.getByRole('button', { name: 'Kiểm tra và kết nối' })
    const cameraUrl = screen.getByRole('textbox', { name: 'URL luồng MJPEG' })
    await user.click(connectButton)
    expect(await screen.findByText('Nhập URL luồng MJPEG từ điện thoại.')).toBeInTheDocument()
    expect(cameraUrl).toHaveFocus()
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    expect(fetchMock.mock.calls.filter(([input]) => String(input) === '/api/camera/connect')).toHaveLength(1)

    await user.type(cameraUrl, 'ftp://192.168.1.20/video')
    await user.click(connectButton)
    expect(await screen.findByText('URL phải bắt đầu bằng http:// hoặc https://.')).toBeInTheDocument()

    await user.clear(cameraUrl)
    await user.type(cameraUrl, 'http://10.64.226.229:8080')
    let resolvePhoneConnection!: (response: Response) => void
    let pendingPhoneRequest: RequestInit | undefined
    cameraResponder = (request) => new Promise<Response>((resolve) => {
      pendingPhoneRequest = request
      resolvePhoneConnection = resolve
      expect(JSON.parse(String(request?.body))).toEqual({
        source_type: 'phone',
        camera_url: 'http://10.64.226.229:8080',
        model_mode: 'yolo11n_behavior_p2',
        conf_threshold: 0.55,
        current_connection_id: 'camera-connection-1',
      })
    })

    await user.click(connectButton)
    expect(await screen.findByRole('button', { name: 'Đang kiểm tra camera…' })).toBeDisabled()
    expect(screen.getByRole('radio', { name: /Camera điện thoại/ })).toBeDisabled()

    resolvePhoneConnection(jsonResponse(cameraResultFromRequest(pendingPhoneRequest)))

    const phoneCandidate = await screen.findByTestId('camera-candidate-stream')
    expect(phoneCandidate).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('Webcam · Camera 0')).toBeInTheDocument()
    fireEvent.load(phoneCandidate)

    expect(await screen.findByText('Điện thoại · 10.64.226.229')).toBeInTheDocument()
    const phoneStream = screen.getByTestId('camera-active-stream')
    expect(phoneStream).toHaveAttribute('src', expect.stringContaining('connection_id=camera-connection-2'))
    expect(phoneStream.getAttribute('src')).not.toContain('10.64.226.229')
    expect(cameraUrl).toHaveValue('http://10.64.226.229:8080/video')
    expect(screen.getByTestId('location-search')).not.toHaveTextContent('camera_url')
    expect(screen.getByTestId('location-search')).not.toHaveTextContent('10.64.226.229')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/camera/connections/camera-connection-1',
      expect.objectContaining({ method: 'DELETE' }),
    ))
  })

  it('keeps the active stream and attempted URL when the connection check fails', async () => {
    const user = userEvent.setup()
    renderRoute('/camera')

    const initialStream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    fireEvent.load(initialStream)
    const initialSrc = initialStream.getAttribute('src')

    cameraResponder = () => Promise.resolve(jsonResponse({
      ok: false,
      error: { code: 'camera_unavailable', message: 'Camera unavailable' },
    }, 503))
    await user.click(screen.getByRole('radio', { name: /Camera điện thoại/ }))
    await user.type(
      screen.getByRole('textbox', { name: 'URL luồng MJPEG' }),
      'http://192.168.1.30:8080/video',
    )
    await user.click(screen.getByRole('button', { name: 'Kiểm tra và kết nối' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Chưa thể kết nối nguồn mới')
    expect(alert).toHaveTextContent('Không thể kết nối tới camera')
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    expect(screen.getByRole('img', { name: 'Luồng camera giám sát kỳ thi' })).toHaveAttribute('src', initialSrc)
    expect(screen.getAllByText('Đã nhận luồng hình').length).toBeGreaterThan(0)
    expect(screen.getByText('Webcam · Camera 0')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'URL luồng MJPEG' })).toHaveValue('http://192.168.1.30:8080/video')
    expect(screen.getByText('AI đang xem xét')).toBeInTheDocument()
  })

  it('restores a different active stream if the new feed cannot render', async () => {
    const user = userEvent.setup()
    renderRoute('/camera')

    const initialStream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    fireEvent.load(initialStream)
    const initialSrc = initialStream.getAttribute('src')

    await user.click(screen.getByRole('radio', { name: /Camera điện thoại/ }))
    const cameraUrl = screen.getByRole('textbox', { name: 'URL luồng MJPEG' })
    await user.type(cameraUrl, 'http://192.168.1.31:8080/video')
    await user.click(screen.getByRole('button', { name: 'Kiểm tra và kết nối' }))

    const candidate = await screen.findByTestId('camera-candidate-stream')
    expect(screen.getByTestId('camera-active-stream')).toHaveAttribute('src', initialSrc)
    fireEvent.error(candidate)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Luồng camera trước đó đã được khôi phục')
    expect(screen.getByTestId('camera-active-stream')).toHaveAttribute('src', initialSrc)
    expect(screen.getByText('Webcam · Camera 0')).toBeInTheDocument()
    expect(cameraUrl).toHaveValue('http://192.168.1.31:8080/video')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/camera/connections/camera-connection-2',
      expect.objectContaining({ method: 'DELETE' }),
    )
    expect(fetchMock).not.toHaveBeenCalledWith(
      '/api/camera/connections/camera-connection-1',
      expect.anything(),
    )
  })

  it('confirms a reused session rollback only after the restored feed loads', async () => {
    const user = userEvent.setup()
    renderRoute('/camera?model_mode=yolo11n_behavior_p2&conf_threshold=0.55', true)

    const initialStream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    fireEvent.load(initialStream)
    const initialSrc = initialStream.getAttribute('src')

    fireEvent.change(screen.getByRole('slider', { name: 'Ngưỡng tin cậy' }), {
      target: { value: '0.8' },
    })
    await user.click(screen.getByRole('button', { name: 'Kiểm tra và kết nối' }))
    const candidate = await screen.findByTestId('camera-candidate-stream')
    expect(screen.queryByTestId('camera-active-stream')).not.toBeInTheDocument()

    fireEvent.error(candidate)
    const restoredStream = await screen.findByTestId('camera-active-stream')
    expect(restoredStream.getAttribute('src')).not.toBe(initialSrc)
    expect(restoredStream).toHaveAttribute('src', expect.stringContaining('conf_threshold=0.55'))
    expect(screen.getByRole('slider', { name: 'Ngưỡng tin cậy' })).toHaveValue('0.8')
    expect(screen.getByTestId('location-search')).toHaveTextContent('conf_threshold=0.55')
    expect(screen.getByRole('alert')).toHaveTextContent('Đang thử khôi phục luồng camera trước đó')
    expect(screen.getByRole('alert')).not.toHaveTextContent('đã được khôi phục')
    expect(screen.getAllByText('Đang kết nối').length).toBeGreaterThan(0)
    expect(fetchMock).not.toHaveBeenCalledWith(
      '/api/camera/connections/camera-connection-1',
      expect.anything(),
    )

    fireEvent.load(restoredStream)

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
    expect(screen.getAllByText('Đã nhận luồng hình').length).toBeGreaterThan(0)
    expect(screen.getByText('AI đang xem xét')).toBeInTheDocument()
  })

  it('reports when a reused session cannot restore its previous feed', async () => {
    const user = userEvent.setup()
    renderRoute('/camera?model_mode=yolo11n_behavior_p2&conf_threshold=0.55', true)

    const initialStream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    fireEvent.load(initialStream)

    fireEvent.change(screen.getByRole('slider', { name: 'Ngưỡng tin cậy' }), {
      target: { value: '0.8' },
    })
    await user.click(screen.getByRole('button', { name: 'Kiểm tra và kết nối' }))

    const candidate = await screen.findByTestId('camera-candidate-stream')
    fireEvent.error(candidate)
    const restoredStream = await screen.findByTestId('camera-active-stream')
    expect(screen.getByRole('alert')).toHaveTextContent('Đang thử khôi phục luồng camera trước đó')

    fireEvent.error(restoredStream)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Không thể khôi phục luồng camera trước đó')
    expect(alert).toHaveTextContent('chọn Kết nối lại')
    expect(screen.getAllByText('Mất kết nối').length).toBeGreaterThan(0)
    expect(screen.getByText('AI đã tạm dừng')).toBeInTheDocument()
  })

  it('releases the active camera session with keepalive when leaving the page', async () => {
    const view = renderRoute('/camera')
    const initialStream = await screen.findByRole('img', { name: 'Luồng camera giám sát kỳ thi' })
    fireEvent.load(initialStream)

    view.unmount()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/camera/connections/camera-connection-1',
      expect.objectContaining({ method: 'DELETE', keepalive: true }),
    )
  })
})
