import { FileImage, ScanSearch } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import {
  analyzeImage,
  getErrorMessage,
  validateUpload,
  type ImageAnalysisResult,
} from '../api/client'
import DetectionTable from '../components/DetectionTable'
import DetectorSettings from '../components/DetectorSettings'
import MediaPanel from '../components/MediaPanel'
import ResultSummary from '../components/ResultSummary'
import StatusNotice, { type NoticeTone } from '../components/StatusNotice'
import ToolPageLayout from '../components/ToolPageLayout'
import UploadDropzone from '../components/UploadDropzone'
import { useApiConfig } from '../hooks/useApiConfig'
import { useObjectUrl } from '../hooks/useObjectUrl'
import imageToolBackground from '../assets/generated/tool-image-exam-desk-v1.webp'

type Notice = { tone: NoticeTone; message: string } | null

function isPhoneAlert(item: ImageAnalysisResult['detections'][number]): boolean {
  return item.is_phone || item.class_id === 1 || item.class_id === 7
}

function ImagePage() {
  const { config, loading: loadingConfig, error: configError } = useApiConfig()
  const [file, setFile] = useState<File | null>(null)
  const [modelMode, setModelMode] = useState(config.defaults.model_mode)
  const [confidence, setConfidence] = useState(config.defaults.conf_threshold)
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState<ImageAnalysisResult | null>(null)
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
      setNotice({ tone: 'error', message: 'Vui lòng chọn một ảnh trước khi phân tích.' })
      return
    }

    const validationMessage = validateUpload(file, config.upload.image, config.upload.max_bytes)
    if (validationMessage) {
      setNotice({ tone: 'error', message: validationMessage })
      return
    }

    setPending(true)
    setResult(null)
    setNotice({ tone: 'loading', message: 'Đang phân tích ảnh và tạo bằng chứng trực quan…' })

    const formData = new FormData()
    formData.append('image_file', file)
    formData.append('model_mode', modelMode)
    formData.append('conf_threshold', String(confidence))

    try {
      const nextResult = await analyzeImage(formData)
      setResult(nextResult)
      setNotice({
        tone: 'success',
        message: nextResult.message || 'Phân tích hoàn tất. Hãy kiểm tra kết quả trước khi đưa ra quyết định.',
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
    <section className="tool-panel" aria-labelledby="image-upload-title" aria-busy={pending}>
      <header className="tool-panel-header">
        <div>
          <h2 id="image-upload-title" className="tool-panel-label">
            <FileImage size={16} className="text-olive" aria-hidden="true" />
            Ảnh cần kiểm tra
          </h2>
          <p className="tool-panel-meta">Ảnh gốc được giữ nguyên; hệ thống tạo một bản đã chú thích riêng.</p>
        </div>
      </header>
      <div className="tool-panel-body">
        <UploadDropzone
          kind="image"
          file={file}
          previewUrl={previewUrl}
          accept={[...config.upload.image.mime_types, ...config.upload.image.extensions].join(',')}
          disabled={pending}
          helper={`${config.upload.image.extensions.join(', ')} · tối đa ${config.upload.max_mb} MB`}
          onFileSelect={selectFile}
        />
        {configError ? <StatusNotice tone="error">{configError} Đang dùng cấu hình dự phòng.</StatusNotice> : null}
        {notice ? <StatusNotice tone={notice.tone}>{notice.message}</StatusNotice> : null}
      </div>
    </section>
  )

  const settings = (
    <DetectorSettings
      config={config}
      modelMode={modelMode}
      confidence={confidence}
      loadingConfig={loadingConfig}
      pending={pending}
      disabled={!file}
      submitLabel="Bắt đầu phân tích"
      pendingLabel="Đang phân tích…"
      onModelChange={setModelMode}
      onConfidenceChange={setConfidence}
    />
  )

  return (
    <ToolPageLayout
      kicker="Nhận diện hình ảnh"
      title="Phân tích ảnh thi cử"
      description="Tải ảnh lên để phát hiện điện thoại, xem khung nhận diện và độ tin cậy. Mọi cảnh báo đều cần giám thị xác minh."
      status={configError ? 'Đang dùng cấu hình dự phòng' : pending ? 'Đang phân tích' : 'Sẵn sàng phân tích'}
      statusTone={configError ? 'coral' : pending ? 'cyan' : 'olive'}
      background={{ src: imageToolBackground, variant: 'image' }}
      workspace={workspace}
      settings={settings}
      busy={pending}
      onSubmit={handleAnalyze}
    >
      {result ? (
        <section ref={resultRef} className="tool-result-section" aria-labelledby="image-result-title">
          <div className="tool-result-heading">
            <div>
              <p className="tool-kicker">Xem xét bằng chứng</p>
              <h2 id="image-result-title" className="tool-result-title">Kết quả nhận diện</h2>
            </div>
            <span className="tool-pill" data-alert={result.detections.some(isPhoneAlert)}>
              <ScanSearch size={14} aria-hidden="true" />
              {result.detections.some(isPhoneAlert) ? 'Cần xem xét' : 'Không có cảnh báo điện thoại'}
            </span>
          </div>

          <ResultSummary
            items={[
              { label: 'Tệp', value: file?.name || 'Ảnh đã tải lên' },
              { label: 'Tổng phát hiện', value: String(result.detections.length) },
              { label: 'Phone · Class 1', value: String(result.detections.filter((item) => item.class_id === 1).length) },
              { label: 'Using Phone · Class 7', value: String(result.detections.filter((item) => item.class_id === 7).length) },
              { label: 'Ngưỡng', value: `${Math.round(result.settings.conf_threshold * 100)}%` },
            ]}
          />

          <div className="tool-media-grid">
            <MediaPanel title="Ảnh gốc" meta="Nguồn bằng chứng chưa chỉnh sửa">
              <img src={result.original_url} alt="Ảnh gốc được tải lên để phân tích" />
            </MediaPanel>
            <MediaPanel title="Ảnh đã nhận diện" meta="Khung nhận diện do mô hình đề xuất">
              <img src={result.output_url} alt="Ảnh kết quả có khung nhận diện" />
            </MediaPanel>
          </div>

          <DetectionTable detections={result.detections} />
        </section>
      ) : null}
    </ToolPageLayout>
  )
}

export default ImagePage
