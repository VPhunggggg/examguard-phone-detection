import { Camera, Smartphone, Video } from 'lucide-react'
import type { CameraSourceType } from '../api/client'

export type CameraSourceDraft = {
  sourceType: CameraSourceType
  cameraIndex: string
  cameraUrl: string
}

export type CameraSourceFieldErrors = {
  cameraIndex?: string
  cameraUrl?: string
}

type CameraSourceSettingsProps = {
  source: CameraSourceDraft
  errors?: CameraSourceFieldErrors
  serverError?: string | null
  pending?: boolean
  onSourceTypeChange: (sourceType: CameraSourceType) => void
  onCameraIndexChange: (cameraIndex: string) => void
  onCameraUrlChange: (cameraUrl: string) => void
}

function CameraSourceSettings({
  source,
  errors = {},
  serverError = null,
  pending = false,
  onSourceTypeChange,
  onCameraIndexChange,
  onCameraUrlChange,
}: CameraSourceSettingsProps) {
  const isWebcam = source.sourceType === 'webcam'

  return (
    <section className="tool-panel tool-source-panel" aria-labelledby="camera-source-title">
      <header className="tool-panel-header">
        <div>
          <h2 id="camera-source-title" className="tool-panel-label">
            <Camera size={16} className="text-cyan" aria-hidden="true" />
            Nguồn camera
          </h2>
          <p className="tool-panel-meta">Chọn camera máy tính hoặc luồng MJPEG từ điện thoại.</p>
        </div>
      </header>

      <div className="tool-panel-body">
        <fieldset className="tool-source-options" disabled={pending}>
          <legend className="sr-only">Loại nguồn camera</legend>

          <label className="tool-source-option" data-selected={isWebcam}>
            <input
              type="radio"
              name="source_type"
              value="webcam"
              checked={isWebcam}
              onChange={() => onSourceTypeChange('webcam')}
            />
            <span className="tool-source-option-icon" aria-hidden="true"><Video size={16} /></span>
            <span>
              <strong>Webcam máy tính</strong>
              <small>Camera USB hoặc tích hợp</small>
            </span>
          </label>

          <label className="tool-source-option" data-selected={!isWebcam}>
            <input
              type="radio"
              name="source_type"
              value="phone"
              checked={!isWebcam}
              onChange={() => onSourceTypeChange('phone')}
            />
            <span className="tool-source-option-icon" aria-hidden="true"><Smartphone size={16} /></span>
            <span>
              <strong>Camera điện thoại</strong>
              <small>Luồng MJPEG trong mạng LAN</small>
            </span>
          </label>
        </fieldset>

        {isWebcam ? (
          <div className="tool-field tool-source-field">
            <div className="tool-label-row">
              <label className="tool-label" htmlFor="camera-index">Số camera</label>
              <span className="tool-field-constraint">0–9</span>
            </div>
            <input
              id="camera-index"
              name="camera_index"
              className="tool-input"
              type="number"
              inputMode="numeric"
              min="0"
              max="9"
              step="1"
              value={source.cameraIndex}
              disabled={pending}
              aria-invalid={Boolean(errors.cameraIndex)}
              aria-describedby={errors.cameraIndex ? 'camera-index-error' : 'camera-index-help'}
              onChange={(event) => onCameraIndexChange(event.target.value)}
            />
            {errors.cameraIndex ? (
              <p id="camera-index-error" className="tool-field-error" role="alert">{errors.cameraIndex}</p>
            ) : (
              <p id="camera-index-help" className="tool-helper">Camera mặc định thường là số 0.</p>
            )}
          </div>
        ) : (
          <div className="tool-field tool-source-field">
            <label className="tool-label tool-label-block" htmlFor="camera-url">URL luồng MJPEG</label>
            <input
              id="camera-url"
              name="camera_url"
              className="tool-input"
              type="url"
              inputMode="url"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              placeholder="http://192.168.1.20:8080/video"
              value={source.cameraUrl}
              disabled={pending}
              aria-invalid={Boolean(errors.cameraUrl)}
              aria-describedby={errors.cameraUrl ? 'camera-url-error camera-url-help' : 'camera-url-help'}
              onChange={(event) => onCameraUrlChange(event.target.value)}
            />
            {errors.cameraUrl ? (
              <p id="camera-url-error" className="tool-field-error" role="alert">{errors.cameraUrl}</p>
            ) : null}
            <p id="camera-url-help" className="tool-helper">
              Mở IP Webcam, bật máy chủ rồi dán địa chỉ ứng dụng hiển thị. Bạn có thể nhập địa chỉ gốc; hệ thống sẽ tự thêm <code>/video</code>. Điện thoại và máy tính phải dùng cùng Wi‑Fi.
            </p>
          </div>
        )}

        {serverError ? (
          <div className="tool-source-error" role="alert">
            <strong>Chưa thể kết nối nguồn mới</strong>
            <span>{serverError}</span>
          </div>
        ) : null}
      </div>
    </section>
  )
}

export default CameraSourceSettings
