export type ModelOption = {
  value: string
  label: string
  available: boolean
  warning: string
}

export type UploadRule = {
  extensions: string[]
  mime_types: string[]
}

export type ApiConfig = {
  ok: true
  model_options: ModelOption[]
  defaults: {
    model_mode: string
    conf_threshold: number
  }
  confidence: {
    min: number
    max: number
    step: number
  }
  upload: {
    max_bytes: number
    max_mb: number
    image: UploadRule
    video: UploadRule
  }
}

export type Detection = {
  label: string
  confidence: number
  class_id: number
  is_phone: boolean
  x1: number
  y1: number
  x2: number
  y2: number
}

export type AnalysisSettings = {
  model_mode: string
  conf_threshold: number
}

export type CameraSourceType = 'webcam' | 'phone'

export type WebcamCameraSource = {
  source_type: 'webcam'
  camera_index: number
}

export type PhoneCameraSource = {
  source_type: 'phone'
  camera_url: string
}

export type CameraSource = WebcamCameraSource | PhoneCameraSource

export type ConnectCameraRequest = CameraSource & AnalysisSettings & {
  current_connection_id?: string
}

export type CameraConnectionResult = {
  ok: true
  connection_id: string
  feed_url: string
  source_label: string
  source: CameraSource
  settings: AnalysisSettings
}

export type ImageAnalysisResult = {
  ok: true
  original_url: string
  output_url: string
  detections: Detection[]
  settings: AnalysisSettings
  message: string
}

export type VideoAnalysisResult = {
  ok: true
  input_url: string
  output_url: string
  settings: AnalysisSettings
  message: string
}

type ApiErrorPayload = {
  ok: false
  error: {
    code: string
    message: string
    max_bytes?: number
    retry_after_seconds?: number
    [key: string]: unknown
  }
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: ApiErrorPayload['error']

  constructor(status: number, details: ApiErrorPayload['error']) {
    super(details.message || 'Không thể hoàn tất yêu cầu.')
    this.name = 'ApiError'
    this.code = details.code
    this.status = status
    this.details = details
  }
}

const DEFAULT_MODEL_MODE = 'yolo11n_behavior_p2'
const PUBLIC_MODEL_MODES = [DEFAULT_MODEL_MODE, 'yolov8n_coco_phone'] as const

export const FALLBACK_CONFIG: ApiConfig = {
  ok: true,
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
    model_mode: DEFAULT_MODEL_MODE,
    conf_threshold: 0.5,
  },
  confidence: {
    min: 0.1,
    max: 0.9,
    step: 0.05,
  },
  upload: {
    max_bytes: 200 * 1024 * 1024,
    max_mb: 200,
    image: {
      extensions: ['.jpg', '.jpeg', '.png'],
      mime_types: ['image/jpeg', 'image/png'],
    },
    video: {
      extensions: ['.mp4', '.avi', '.mov'],
      mime_types: ['video/mp4', 'video/quicktime', 'video/x-msvideo'],
    },
  },
}

function sanitizeApiConfig(config: ApiConfig): ApiConfig {
  const modelOptions = PUBLIC_MODEL_MODES.flatMap((modelMode) => {
    const option = config.model_options.find((candidate) => candidate.value === modelMode)
    return option ? [option] : []
  })

  return {
    ...config,
    model_options: modelOptions,
    defaults: {
      ...config.defaults,
      model_mode: DEFAULT_MODEL_MODE,
    },
  }
}

let configRequest: Promise<ApiConfig> | null = null

async function readJson<T>(response: Response): Promise<T> {
  let payload: unknown

  try {
    payload = await response.json()
  } catch {
    throw new ApiError(response.status, {
      code: 'invalid_response',
      message: 'Máy chủ trả về dữ liệu không hợp lệ.',
    })
  }

  if (!response.ok || (payload as ApiErrorPayload)?.ok === false) {
    const details = (payload as ApiErrorPayload)?.error ?? {
      code: 'request_failed',
      message: 'Không thể hoàn tất yêu cầu.',
    }
    throw new ApiError(response.status, details)
  }

  return payload as T
}

export function getApiConfig(): Promise<ApiConfig> {
  if (!configRequest) {
    configRequest = fetch('/api/config', {
      headers: { Accept: 'application/json' },
    })
      .then((response) => readJson<ApiConfig>(response))
      .then(sanitizeApiConfig)
      .catch((error: unknown) => {
        configRequest = null
        throw error
      })
  }

  return configRequest
}

async function postAnalysis<T>(endpoint: string, formData: FormData): Promise<T> {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { Accept: 'application/json' },
    body: formData,
  })
  return readJson<T>(response)
}

export function analyzeImage(formData: FormData): Promise<ImageAnalysisResult> {
  return postAnalysis<ImageAnalysisResult>('/api/image', formData)
}

export function analyzeVideo(formData: FormData): Promise<VideoAnalysisResult> {
  return postAnalysis<VideoAnalysisResult>('/api/video', formData)
}

export async function connectCamera(payload: ConnectCameraRequest): Promise<CameraConnectionResult> {
  const response = await fetch('/api/camera/connect', {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return readJson<CameraConnectionResult>(response)
}

export async function releaseCameraConnection(
  connectionId: string,
  options: { keepalive?: boolean } = {},
): Promise<void> {
  const response = await fetch(`/api/camera/connections/${encodeURIComponent(connectionId)}`, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
    keepalive: options.keepalive,
  })
  if (!response.ok) {
    await readJson<unknown>(response)
  }
}

function hasVietnameseDiacritics(message: string): boolean {
  return /[À-ỹĐđ]/u.test(message)
}

function getVietnameseApiMessage(error: ApiError): string {
  const serverMessage = error.message.trim()

  if (hasVietnameseDiacritics(serverMessage)) {
    return serverMessage
  }

  switch (error.code) {
    case 'invalid_upload':
      return 'Tệp tải lên không hợp lệ. Vui lòng kiểm tra định dạng và thử lại.'
    case 'file_too_large': {
      const maxBytes = Number(error.details.max_bytes)
      return Number.isFinite(maxBytes) && maxBytes > 0
        ? `Tệp vượt quá giới hạn ${Math.max(1, Math.round(maxBytes / 1024 / 1024))} MB.`
        : 'Tệp tải lên vượt quá giới hạn dung lượng.'
    }
    case 'processing_failed':
      return serverMessage.toLocaleLowerCase('en-US').includes('video')
        ? 'Không thể xử lý video đã tải lên.'
        : 'Không thể xử lý ảnh đã tải lên.'
    case 'rate_limited':
      return 'Có quá nhiều yêu cầu.'
    case 'video_busy':
      return 'Một video khác đang được xử lý. Vui lòng đợi hoàn tất rồi thử lại.'
    case 'detector_unavailable':
      return 'Bộ nhận diện đã chọn hiện chưa sẵn sàng. Hãy kiểm tra tệp model rồi thử lại.'
    case 'invalid_camera_source':
      return 'Nguồn camera không hợp lệ. Vui lòng kiểm tra thông tin đã nhập.'
    case 'camera_unavailable':
      return 'Không thể kết nối tới camera. Hãy kiểm tra thiết bị, địa chỉ mạng và thử lại.'
    case 'frontend_unavailable':
      return 'Giao diện hiện chưa sẵn sàng.'
    case 'not_found':
      return 'Không tìm thấy nội dung được yêu cầu.'
    case 'internal_error':
      return 'Máy chủ gặp lỗi nội bộ. Vui lòng thử lại sau.'
    case 'invalid_response':
      return 'Máy chủ trả về dữ liệu không hợp lệ.'
    default:
      return 'Không thể hoàn tất yêu cầu.'
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const message = getVietnameseApiMessage(error)
    if (error.code === 'rate_limited' && error.details.retry_after_seconds) {
      return `${message} Vui lòng thử lại sau ${error.details.retry_after_seconds} giây.`
    }
    return message
  }
  return 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại và thử lần nữa.'
}

export function validateUpload(file: File, rule: UploadRule, maxBytes: number): string | null {
  if (file.size > maxBytes) {
    return `Tệp vượt quá giới hạn ${Math.max(1, Math.round(maxBytes / 1024 / 1024))} MB.`
  }

  const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
  if (!rule.extensions.map((item) => item.toLowerCase()).includes(extension)) {
    return `Định dạng không được hỗ trợ. Hãy dùng ${rule.extensions.join(', ')}.`
  }

  if (file.type && !rule.mime_types.includes(file.type)) {
    return 'Loại nội dung của tệp không hợp lệ.'
  }

  return null
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
