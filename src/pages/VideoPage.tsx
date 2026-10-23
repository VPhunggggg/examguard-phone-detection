import { Film, PlaySquare } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import {
  analyzeVideo,
  getErrorMessage,
  validateUpload,
  type VideoAnalysisResult,
} from '../api/client'
import DetectorSettings from '../components/DetectorSettings'
import MediaPanel from '../components/MediaPanel'
import ResultSummary from '../components/ResultSummary'
import StatusNotice, { type NoticeTone } from '../components/StatusNotice'
import ToolPageLayout from '../components/ToolPageLayout'
import UploadDropzone from '../components/UploadDropzone'
import { useApiConfig } from '../hooks/useApiConfig'
import { useObjectUrl } from '../hooks/useObjectUrl'
import videoToolBackground from '../assets/generated/tool-video-exam-review-v1.webp'
import { getVietnameseModelValueLabel } from '../utils/vietnamese'

type Notice = { tone: NoticeTone; message: string } | null

function VideoPage() {
  const { config, loading: loadingConfig, error: configError } = useApiConfig()
  const [file, setFile] = useState<File | null>(null)
  const [modelMode, setModelMode] = useState(config.defaults.model_mode)
  const [confidence, setConfidence] = useState(config.defaults.conf_threshold)
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<VideoAnalysisResult | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const defaultsApplied = useRef(false)
  const resultRef = useRef<HTMLElement>(null)
  const previewUrl = useObjectUrl(file)

  useEffect(() => {
    if (!loadingConfig && !defaultsApplied.current) {
      setModelMode(config.defaults.model_mode)
      setConfidence(config.defaults.conf_threshold)
      defaultsApplied.current = true
    }
  }, [config, loadingConfig])

  const selectFile = (nextFile: File) => {
    setFile(nextFile)
    setResult(null)
    setNotice(null)
  }

  const handleAnalyze = async () => {
    if (pending) return
    if (!file) {
      setNotice({ tone: 'error', message: 'Vui lòng chọn một video trước khi xử lý.' })
      return
    }

    const validationMessage = validateUpload(file, config.upload.video, config.upload.max_bytes)
    if (validationMessage) {
      setNotice({ tone: 'error', message: validationMessage })
      return
    }

    setPending(true)
    setResult(null)
    setNotice({ tone: 'loading', message: 'Đang xử lý video, vui lòng không đóng trang.' })

    const formData = new FormData()
    formData.append('video_file', file)
    formData.append('model_mode', modelMode)
    formData.append('conf_threshold', String(confidence))

    try {
      const nextResult = await analyzeVideo(formData)
      setResult(nextResult)
      setNotice({
        tone: 'success',
        message: nextResult.message || 'Video đã được xử lý và sẵn sàng để xem lại.',
      })
      window.requestAnimationFrame(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    } catch (error: unknown) {
      setNotice({ tone: 'error', message: getErrorMessage(error) })
    } finally {
      setPending(false)
    }
  }

  const workspace = (
    <section className="tool-panel" aria-labelledby="video-upload-title" aria-busy={pending}>
      <header className="tool-panel-header">
        <div>
          <h2 id="video-upload-title" className="tool-panel-label">
            <Film size={16} className="text-olive" aria-hidden="true" />
            Video cần kiểm tra
          </h2>
          <p className="tool-panel-meta">Thời gian xử lý phụ thuộc độ dài video và cấu hình máy.</p>
        </div>
      </header>
      <div className="tool-panel-body">
        <UploadDropzone
          kind="video"
          file={file}
          previewUrl={previewUrl}
          accept={[...config.upload.video.mime_types, ...config.upload.video.extensions].join(',')}
          disabled={pending}
          helper={`${config.upload.video.extensions.join(', ')} · tối đa ${config.upload.max_mb} MB`}
          onFileSelect={selectFile}
        />
        {configError ? <StatusNotice tone="error">{configError} Đang dùng cấu hình dự phòng.</StatusNotice> : null}
        {notice ? <StatusNotice tone={notice.tone}>{notice.message}</StatusNotice> : null}
      </div>
    </section>
  )

  return (
    <ToolPageLayout
      kicker="Bằng chứng video"
      title="Phân tích video kỳ thi"
      description="Xử lý từng khung hình, đánh dấu dấu hiệu sử dụng điện thoại và xuất video phục vụ quá trình xem xét."
      status={configError ? 'Đang dùng cấu hình dự phòng' : pending ? 'Đang xử lý video' : 'Sẵn sàng xử lý'}
      statusTone={configError ? 'coral' : pending ? 'cyan' : 'olive'}
      background={{ src: videoToolBackground, variant: 'video' }}
      workspace={workspace}
      busy={pending}
      onSubmit={handleAnalyze}
      settings={(
        <DetectorSettings
          config={config}
          modelMode={modelMode}
          confidence={confidence}
          loadingConfig={loadingConfig}
          pending={pending}
          disabled={!file}
          submitLabel="Xử lý video"
          pendingLabel="Đang xử lý…"
          onModelChange={setModelMode}
          onConfidenceChange={setConfidence}
        />
      )}
    >
      {result ? (
        <section ref={resultRef} className="tool-result-section" aria-labelledby="video-result-title">
          <div className="tool-result-heading">
            <div>
              <p className="tool-kicker">Sẵn sàng xem xét</p>
              <h2 id="video-result-title" className="tool-result-title">Video đã xử lý</h2>
            </div>
            <span className="tool-pill"><PlaySquare size={14} aria-hidden="true" /> Sẵn sàng xem lại</span>
          </div>

          <ResultSummary
            items={[
              { label: 'Tệp', value: file?.name || 'Video đã tải lên' },
              { label: 'Mô hình', value: getVietnameseModelValueLabel(result.settings.model_mode) },
              { label: 'Ngưỡng', value: `${Math.round(result.settings.conf_threshold * 100)}%` },
              { label: 'Trạng thái', value: 'Hoàn tất' },
            ]}
          />

          <div className="tool-media-grid">
            <MediaPanel title="Video gốc" meta="Nguồn bằng chứng chưa chỉnh sửa">
              <video src={result.input_url} controls playsInline preload="metadata">
                Trình duyệt không hỗ trợ phát video.
              </video>
            </MediaPanel>
            <MediaPanel title="Video đã nhận diện" meta="Khung hình có chú thích từ mô hình">
              <video src={result.output_url} controls playsInline preload="metadata">
                Trình duyệt không hỗ trợ phát video.
              </video>
            </MediaPanel>
          </div>
        </section>
      ) : null}
    </ToolPageLayout>
  )
}

export default VideoPage
