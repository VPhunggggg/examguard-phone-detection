import { beforeEach, describe, expect, it, vi } from 'vitest'

const API_CONFIG = {
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
      extensions: ['.jpg', '.png'],
      mime_types: ['image/jpeg', 'image/png'],
    },
    video: {
      extensions: ['.mp4'],
      mime_types: ['video/mp4'],
    },
  },
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it('uses only Phone + Using Phone and Phone while keeping behavior detection as default', async () => {
    const { FALLBACK_CONFIG } = await import('./client')

    expect(FALLBACK_CONFIG.model_options).toEqual([
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
    ])
    expect(FALLBACK_CONFIG.defaults.model_mode).toBe('yolo11n_behavior_p2')
  })

  it('filters a stale API config to the two public models and canonicalizes its default', async () => {
    const staleConfig = {
      ...API_CONFIG,
      model_options: [
        {
          value: 'examguard_vision_system',
          label: 'ExamGuard Vision System',
          available: true,
          warning: '',
        },
        API_CONFIG.model_options[1],
        API_CONFIG.model_options[0],
        {
          value: 'yolo12n_behavior_p2',
          label: 'YOLO12n Behavior P2',
          available: true,
          warning: '',
        },
      ],
      defaults: {
        ...API_CONFIG.defaults,
        model_mode: 'examguard_vision_system',
      },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(staleConfig)))

    const { getApiConfig } = await import('./client')
    const config = await getApiConfig()

    expect(config.model_options).toEqual(API_CONFIG.model_options)
    expect(config.defaults.model_mode).toBe('yolo11n_behavior_p2')
  })

  it('loads and shares the API configuration request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(API_CONFIG))
    vi.stubGlobal('fetch', fetchMock)

    const { getApiConfig } = await import('./client')
    const [first, second] = await Promise.all([getApiConfig(), getApiConfig()])

    expect(first).toEqual(API_CONFIG)
    expect(second).toBe(first)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/config', {
      headers: { Accept: 'application/json' },
    })
  })

  it('posts image and video data to their dedicated endpoints', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ ok: true, kind: 'image' }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, kind: 'video' }))
    vi.stubGlobal('fetch', fetchMock)

    const { analyzeImage, analyzeVideo } = await import('./client')
    const imageData = new FormData()
    const videoData = new FormData()

    await analyzeImage(imageData)
    await analyzeVideo(videoData)

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/image', {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body: imageData,
    })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/video', {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body: videoData,
    })
  })

  it('surfaces the structured API error and retry guidance', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(jsonResponse({
      ok: false,
      error: {
        code: 'rate_limited',
        message: 'Quá nhiều yêu cầu.',
        retry_after_seconds: 12,
      },
    }, 429))))

    const { analyzeImage, getErrorMessage } = await import('./client')

    await expect(analyzeImage(new FormData())).rejects.toMatchObject({
      code: 'rate_limited',
      status: 429,
    })

    try {
      await analyzeImage(new FormData())
    } catch (error: unknown) {
      expect(getErrorMessage(error)).toBe('Quá nhiều yêu cầu. Vui lòng thử lại sau 12 giây.')
    }
  })
})
