import { Camera, RadioTower, RefreshCw, Video, WifiOff } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  connectCamera,
  getErrorMessage,
  releaseCameraConnection,
  type CameraConnectionResult,
  type ConnectCameraRequest,
} from '../api/client'
import CameraSourceSettings, {
  type CameraSourceDraft,
  type CameraSourceFieldErrors,
} from '../components/CameraSourceSettings'
import DetectorSettings from '../components/DetectorSettings'
import StatusNotice from '../components/StatusNotice'
import ToolPageLayout from '../components/ToolPageLayout'
import { useApiConfig } from '../hooks/useApiConfig'
import cameraToolBackground from '../assets/generated/tool-camera-live-room-v1.webp'

type StreamState = 'connecting' | 'live' | 'error'
type DetectorDraft = { modelMode: string; confidence: number }
type CameraView = { connection: CameraConnectionResult; version: number }

const DEFAULT_SOURCE: CameraSourceDraft = {
  sourceType: 'webcam',
  cameraIndex: '0',
  cameraUrl: '',
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function getSourceRequest(
  source: CameraSourceDraft,
  detector: DetectorDraft,
): { request?: ConnectCameraRequest; errors: CameraSourceFieldErrors } {
  if (source.sourceType === 'webcam') {
    const cameraIndex = Number(source.cameraIndex)
    if (
      source.cameraIndex.trim() === ''
      || !Number.isInteger(cameraIndex)
      || cameraIndex < 0
      || cameraIndex > 9
    ) {
      return { errors: { cameraIndex: 'Số camera phải là số nguyên từ 0 đến 9.' } }
    }

    return {
      errors: {},
      request: {
        source_type: 'webcam',
        camera_index: cameraIndex,
        model_mode: detector.modelMode,
        conf_threshold: detector.confidence,
      },
    }
  }

  const cameraUrl = source.cameraUrl.trim()
  if (!cameraUrl) {
    return { errors: { cameraUrl: 'Nhập URL luồng MJPEG từ điện thoại.' } }
  }

  try {
    const parsedUrl = new URL(cameraUrl)
    if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
      return { errors: { cameraUrl: 'URL phải bắt đầu bằng http:// hoặc https://.' } }
    }
    if (parsedUrl.username || parsedUrl.password) {
      return { errors: { cameraUrl: 'URL camera không được chứa tên đăng nhập hoặc mật khẩu.' } }
    }
  } catch {
    return { errors: { cameraUrl: 'URL camera chưa đúng định dạng.' } }
  }

  return {
    errors: {},
    request: {
      source_type: 'phone',
      camera_url: cameraUrl,
      model_mode: detector.modelMode,
      conf_threshold: detector.confidence,
    },
  }
}

function addReconnectVersion(feedUrl: string, version: number): string {
  const separator = feedUrl.includes('?') ? '&' : '?'
  return `${feedUrl}${separator}reconnect=${version}`
}

function CameraPage() {
  const { config, loading: loadingConfig, error: configError } = useApiConfig()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [draftDetector, setDraftDetector] = useState<DetectorDraft>({
    modelMode: config.defaults.model_mode,
    confidence: config.defaults.conf_threshold,
  })
  const [draftSource, setDraftSource] = useState<CameraSourceDraft>(DEFAULT_SOURCE)
  const [activeView, setActiveView] = useState<CameraView | null>(null)
  const [candidateView, setCandidateView] = useState<CameraView | null>(null)
  const [candidateReady, setCandidateReady] = useState(false)
  const [streamState, setStreamState] = useState<StreamState>('connecting')
  const [connectionPending, setConnectionPending] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<CameraSourceFieldErrors>({})
  const initialConnectionStarted = useRef(false)
  const mountedRef = useRef(true)
  const attemptVersionRef = useRef(0)
  const activeViewRef = useRef<CameraView | null>(null)
  const candidateViewRef = useRef<CameraView | null>(null)
  const streamStateRef = useRef<StreamState>('connecting')
  const candidateFallbackStateRef = useRef<StreamState>('error')
  const restorationPendingRef = useRef(false)
  const paramsKey = searchParams.toString()

  const queryDetector = useMemo<DetectorDraft>(() => {
    const params = new URLSearchParams(paramsKey)
    const requestedModel = params.get('model_mode')
    const modelMode = config.model_options.find(
      (option) => option.value === requestedModel && option.available,
    )?.value ?? config.defaults.model_mode
    const requestedConfidenceValue = params.get('conf_threshold')
    const requestedConfidence = Number(requestedConfidenceValue)
    const confidence = requestedConfidenceValue !== null && Number.isFinite(requestedConfidence)
      ? clamp(requestedConfidence, config.confidence.min, config.confidence.max)
      : config.defaults.conf_threshold

    return { modelMode, confidence }
  }, [config, paramsKey])
  const canonicalParamsKey = useMemo(() => new URLSearchParams({
    model_mode: queryDetector.modelMode,
    conf_threshold: String(queryDetector.confidence),
  }).toString(), [queryDetector])
  const queryModelAvailable = config.model_options.some(
    (option) => option.value === queryDetector.modelMode && option.available,
  )

  const setCurrentStreamState = (state: StreamState) => {
    streamStateRef.current = state
    setStreamState(state)
  }

  const releaseBestEffort = (connectionId: string, keepalive = false) => {
    void releaseCameraConnection(connectionId, { keepalive }).catch(() => undefined)
  }

  const syncDraftFromConnection = (connection: CameraConnectionResult) => {
    setDraftDetector({
      modelMode: connection.settings.model_mode,
      confidence: connection.settings.conf_threshold,
    })
    setDraftSource((current) => (
      connection.source.source_type === 'webcam'
        ? {
            ...current,
            sourceType: 'webcam',
            cameraIndex: String(connection.source.camera_index),
          }
        : {
            ...current,
            sourceType: 'phone',
            cameraUrl: connection.source.camera_url,
          }
    ))
  }

  const replaceDetectorQuery = (connection: CameraConnectionResult) => {
    const params = new URLSearchParams({
      model_mode: connection.settings.model_mode,
      conf_threshold: String(connection.settings.conf_threshold),
    })
    navigate({ search: `?${params.toString()}` }, { replace: true })
  }

  const queueCandidate = (connection: CameraConnectionResult) => {
    const currentActive = activeViewRef.current
    const reusesActiveConnection = Boolean(
      currentActive
      && currentActive.connection.connection_id === connection.connection_id,
    )
    candidateFallbackStateRef.current = currentActive ? streamStateRef.current : 'error'
    restorationPendingRef.current = false
    const view = {
      connection,
      version: ++attemptVersionRef.current,
    }
    candidateViewRef.current = view
    // A reused backend session only permits one MJPEG consumer. Hide/unmount the
    // current image first, then mount the replacement on the following task.
    setCandidateReady(!reusesActiveConnection)
    setCandidateView(view)
    setCurrentStreamState('connecting')
  }

  const connectCandidate = async (request: ConnectCameraRequest) => {
    const currentConnectionId = activeViewRef.current?.connection.connection_id
    const payload = currentConnectionId
      ? { ...request, current_connection_id: currentConnectionId }
      : request
    const hadActiveStream = activeViewRef.current !== null
    setConnectionPending(true)
    setConnectionError(null)
    setFieldErrors({})

    try {
      const result = await connectCamera(payload)
      if (!mountedRef.current) {
        releaseBestEffort(result.connection_id, true)
        return
      }
      queueCandidate(result)
    } catch (error) {
      if (!mountedRef.current) return
      setConnectionError(getErrorMessage(error))
      if (!hadActiveStream) setCurrentStreamState('error')
    } finally {
      if (mountedRef.current) setConnectionPending(false)
    }
  }

  useEffect(() => {
    if (loadingConfig) return

    setDraftDetector(queryDetector)
    if (canonicalParamsKey !== paramsKey) {
      setSearchParams(new URLSearchParams(canonicalParamsKey), { replace: true })
    }
  }, [canonicalParamsKey, loadingConfig, paramsKey, queryDetector, setSearchParams])

  useEffect(() => {
    if (
      loadingConfig
      || canonicalParamsKey !== paramsKey
      || initialConnectionStarted.current
    ) return
    initialConnectionStarted.current = true
    if (!queryModelAvailable) return

    void connectCandidate({
      source_type: 'webcam',
      camera_index: 0,
      model_mode: queryDetector.modelMode,
      conf_threshold: queryDetector.confidence,
    })
  }, [canonicalParamsKey, loadingConfig, paramsKey, queryDetector, queryModelAvailable])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      const connectionIds = new Set([
        activeViewRef.current?.connection.connection_id,
        candidateViewRef.current?.connection.connection_id,
      ].filter((connectionId): connectionId is string => Boolean(connectionId)))
      connectionIds.forEach((connectionId) => releaseBestEffort(connectionId, true))
    }
  }, [])

  useEffect(() => {
    if (
      !candidateView
      || !activeView
      || candidateView.connection.connection_id !== activeView.connection.connection_id
    ) return

    const timer = window.setTimeout(() => {
      if (mountedRef.current && candidateViewRef.current === candidateView) {
        setCandidateReady(true)
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [activeView, candidateView])

  const applySettings = async () => {
    const selectedModel = config.model_options.find(
      (option) => option.value === draftDetector.modelMode && option.available,
    )
    if (!selectedModel) return

    const detector = {
      modelMode: selectedModel.value,
      confidence: clamp(
        draftDetector.confidence,
        config.confidence.min,
        config.confidence.max,
      ),
    }
    const { request, errors } = getSourceRequest(draftSource, detector)
    setFieldErrors(errors)
    if (!request) {
      const invalidFieldId = errors.cameraUrl ? 'camera-url' : 'camera-index'
      document.getElementById(invalidFieldId)?.focus()
      return
    }

    await connectCandidate(request)
  }

  const reconnect = async () => {
    const activeConnection = activeViewRef.current?.connection
    if (activeConnection) {
      await connectCandidate({
        ...activeConnection.source,
        ...activeConnection.settings,
      })
      return
    }
    await applySettings()
  }

  const handleCandidateLoad = (loadedView: CameraView) => {
    const candidate = candidateViewRef.current
    if (!candidate || candidate !== loadedView) return

    const previous = activeViewRef.current
    activeViewRef.current = candidate
    candidateViewRef.current = null
    setActiveView(candidate)
    setCandidateView(null)
    setCandidateReady(false)
    restorationPendingRef.current = false
    setConnectionError(null)
    setCurrentStreamState('live')
    syncDraftFromConnection(candidate.connection)
    replaceDetectorQuery(candidate.connection)

    if (
      previous
      && previous.connection.connection_id !== candidate.connection.connection_id
    ) {
      releaseBestEffort(previous.connection.connection_id)
    }
  }

  const handleCandidateError = (failedView: CameraView) => {
    const candidate = candidateViewRef.current
    if (!candidate || candidate !== failedView) return

    const fallback = activeViewRef.current
    if (
      !fallback
      || fallback.connection.connection_id !== candidate.connection.connection_id
    ) {
      releaseBestEffort(candidate.connection.connection_id)
    }
    candidateViewRef.current = null
    setCandidateView(null)
    setCandidateReady(false)

    if (fallback) {
      if (fallback.connection.connection_id === candidate.connection.connection_id) {
        const restoredView = {
          ...fallback,
          version: ++attemptVersionRef.current,
        }
        activeViewRef.current = restoredView
        setActiveView(restoredView)
        restorationPendingRef.current = true
        setCurrentStreamState('connecting')
        setConnectionError('Không nhận được khung hình mới. Đang thử khôi phục luồng camera trước đó…')
      } else {
        setCurrentStreamState(candidateFallbackStateRef.current)
        setConnectionError('Không nhận được khung hình từ nguồn mới. Luồng camera trước đó đã được khôi phục.')
      }
    } else {
      restorationPendingRef.current = false
      setCurrentStreamState('error')
      setConnectionError('Không nhận được khung hình từ camera vừa kết nối.')
    }
  }

  const handleActiveLoad = (loadedView: CameraView) => {
    if (activeViewRef.current !== loadedView || candidateViewRef.current) return
    if (restorationPendingRef.current) {
      restorationPendingRef.current = false
      setConnectionError(null)
    }
    setCurrentStreamState('live')
  }

  const handleActiveError = (failedView: CameraView) => {
    if (activeViewRef.current !== failedView) return
    if (restorationPendingRef.current) {
      restorationPendingRef.current = false
      setConnectionError('Không thể khôi phục luồng camera trước đó. Hãy kiểm tra nguồn camera rồi chọn Kết nối lại.')
    }
    candidateFallbackStateRef.current = 'error'
    setCurrentStreamState('error')
  }

  const clearSourceError = () => {
    setConnectionError(null)
    setFieldErrors({})
  }

  const detectorUnavailable = Boolean(
    !loadingConfig
    && !connectionPending
    && !activeView
    && !candidateView
    && !queryModelAvailable,
  )
  const stateLabel = detectorUnavailable ? 'Chưa sẵn sàng' : {
    connecting: 'Đang kết nối',
    live: 'Đã nhận luồng hình',
    error: 'Mất kết nối',
  }[streamState]
  const aiStatusLabel = detectorUnavailable ? 'AI đã tạm dừng' : {
    connecting: 'Đang chờ khung hình',
    live: 'AI đang xem xét',
    error: 'AI đã tạm dừng',
  }[streamState]
  const pageStatus = connectionPending
    ? 'Đang kiểm tra nguồn camera'
    : detectorUnavailable
      ? 'Bộ nhận diện chưa sẵn sàng'
      : stateLabel
  const visibleConnection = activeView?.connection ?? candidateView?.connection
  const activeSourceLabel = visibleConnection?.source_label ?? 'Webcam · Camera 0'
  const controlsPending = loadingConfig || connectionPending || candidateView !== null
  const showConnectingOverlay = loadingConfig
    || (!detectorUnavailable && streamState === 'connecting' && !activeView)
  const sameSessionCandidate = Boolean(
    activeView
    && candidateView
    && activeView.connection.connection_id === candidateView.connection.connection_id,
  )
  const showActiveStream = Boolean(activeView && !sameSessionCandidate)
  const hideCandidateStream = Boolean(activeView && !sameSessionCandidate)

  const workspace = (
    <section className="tool-panel" aria-labelledby="camera-stage-title">
      <header className="tool-panel-header">
        <div>
          <h2 id="camera-stage-title" className="tool-panel-label">
            <Camera size={16} className="text-cyan" aria-hidden="true" />
            Camera trực tiếp
          </h2>
          <p className="tool-panel-meta">Luồng MJPEG được xử lý tại máy chủ và hiển thị trực tiếp.</p>
        </div>
      </header>

      <div
        className="tool-camera-stage"
        aria-live="polite"
        aria-busy={!detectorUnavailable && streamState === 'connecting'}
      >
        {showActiveStream && activeView ? (
          <img
            key={`${activeView.connection.connection_id}:${activeView.version}`}
            className="tool-camera-stream"
            data-testid="camera-active-stream"
            src={addReconnectVersion(activeView.connection.feed_url, activeView.version)}
            alt="Luồng camera giám sát kỳ thi"
            loading="eager"
            fetchPriority="high"
            decoding="async"
            draggable={false}
            onLoad={() => handleActiveLoad(activeView)}
            onError={() => handleActiveError(activeView)}
          />
        ) : null}

        {candidateView && candidateReady ? (
          <img
            key={`${candidateView.connection.connection_id}:${candidateView.version}`}
            className={`tool-camera-stream${hideCandidateStream ? ' tool-camera-stream-candidate' : ''}`}
            data-testid="camera-candidate-stream"
            src={addReconnectVersion(candidateView.connection.feed_url, candidateView.version)}
            alt={hideCandidateStream ? '' : 'Luồng camera giám sát kỳ thi'}
            aria-hidden={hideCandidateStream ? 'true' : undefined}
            loading="eager"
            fetchPriority="high"
            decoding="async"
            draggable={false}
            onLoad={() => handleCandidateLoad(candidateView)}
            onError={() => handleCandidateError(candidateView)}
          />
        ) : null}

        <div className="tool-camera-toolbar">
          <div className="tool-camera-toolbar-group">
            <span className="tool-live-state" data-state={streamState}>{stateLabel}</span>
            <span className="tool-live-state tool-source-state">
              <Video size={12} aria-hidden="true" /> {activeSourceLabel}
            </span>
          </div>
          <span className="tool-live-state tool-ai-state" data-state={streamState}>
            <RadioTower size={12} aria-hidden="true" /> {aiStatusLabel}
          </span>
        </div>

        {showConnectingOverlay ? (
          <div className="tool-camera-overlay">
            <div>
              <span className="tool-empty-icon"><RefreshCw className="tool-spin-icon" size={20} aria-hidden="true" /></span>
              <h3 className="tool-empty-title">Đang kết nối luồng camera</h3>
              <p className="tool-empty-copy">Khung hình đầu tiên có thể mất vài giây để xuất hiện.</p>
            </div>
          </div>
        ) : null}

        {streamState === 'error' ? (
          <div className="tool-camera-overlay" role={connectionError ? undefined : 'alert'}>
            <div>
              <span className="tool-empty-icon tool-empty-icon-alert"><WifiOff size={20} aria-hidden="true" /></span>
              <h3 className="tool-empty-title">Không nhận được luồng camera</h3>
              <p className="tool-empty-copy">Kiểm tra nguồn camera trên máy chủ, sau đó thử kết nối lại.</p>
              <button
                className="tool-secondary-button tool-reconnect-button"
                type="button"
                disabled={controlsPending}
                onClick={() => void reconnect()}
              >
                <RefreshCw className={controlsPending ? 'tool-spin-icon' : undefined} size={14} aria-hidden="true" />
                {controlsPending ? 'Đang kiểm tra camera…' : 'Kết nối lại'}
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {configError ? (
        <div className="tool-panel-body tool-panel-body-compact">
          <StatusNotice tone="error">{`${configError} Đang dùng cấu hình dự phòng.`}</StatusNotice>
        </div>
      ) : null}
    </section>
  )

  return (
    <ToolPageLayout
      kicker="Giám sát trực tiếp"
      title="Giám sát camera trực tiếp"
      description="Theo dõi luồng camera theo thời gian thực và làm nổi bật các khung hình cần giám thị chú ý."
      status={configError ? 'Đang dùng cấu hình dự phòng' : pageStatus}
      statusTone={configError || detectorUnavailable || streamState === 'error' ? 'coral' : 'cyan'}
      background={{ src: cameraToolBackground, variant: 'camera' }}
      workspace={workspace}
      busy={controlsPending || (!detectorUnavailable && streamState === 'connecting')}
      onSubmit={() => void applySettings()}
      settings={(
        <div className="tool-settings-stack">
          <CameraSourceSettings
            source={draftSource}
            errors={fieldErrors}
            serverError={connectionError}
            pending={controlsPending}
            onSourceTypeChange={(sourceType) => {
              clearSourceError()
              setDraftSource((current) => ({ ...current, sourceType }))
            }}
            onCameraIndexChange={(cameraIndex) => {
              clearSourceError()
              setDraftSource((current) => ({ ...current, cameraIndex }))
            }}
            onCameraUrlChange={(cameraUrl) => {
              clearSourceError()
              setDraftSource((current) => ({ ...current, cameraUrl }))
            }}
          />
          <DetectorSettings
            config={config}
            modelMode={draftDetector.modelMode}
            confidence={draftDetector.confidence}
            loadingConfig={loadingConfig}
            pending={connectionPending || candidateView !== null}
            submitLabel="Kiểm tra và kết nối"
            pendingLabel="Đang kiểm tra camera…"
            submitIcon="refresh"
            onModelChange={(modelMode) => {
              setConnectionError(null)
              setDraftDetector((current) => ({ ...current, modelMode }))
            }}
            onConfidenceChange={(confidence) => {
              setConnectionError(null)
              setDraftDetector((current) => ({ ...current, confidence }))
            }}
          />
        </div>
      )}
    />
  )
}

export default CameraPage
