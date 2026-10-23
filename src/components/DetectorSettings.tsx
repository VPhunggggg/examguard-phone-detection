import { ArrowRight, LoaderCircle, RefreshCw, Settings2 } from 'lucide-react'
import type { ApiConfig } from '../api/client'
import { getVietnameseModelLabel, getVietnameseModelWarning } from '../utils/vietnamese'

type DetectorSettingsProps = {
  config: ApiConfig
  modelMode: string
  confidence: number
  loadingConfig?: boolean
  pending?: boolean
  submitLabel: string
  pendingLabel?: string
  submitIcon?: 'arrow' | 'refresh'
  disabled?: boolean
  onModelChange: (value: string) => void
  onConfidenceChange: (value: number) => void
}

function DetectorSettings({
  config,
  modelMode,
  confidence,
  loadingConfig = false,
  pending = false,
  submitLabel,
  pendingLabel = 'Đang xử lý…',
  submitIcon = 'arrow',
  disabled = false,
  onModelChange,
  onConfidenceChange,
}: DetectorSettingsProps) {
  const selectedModel = config.model_options.find((model) => model.value === modelMode)
  const SubmitIcon = pending ? LoaderCircle : submitIcon === 'refresh' ? RefreshCw : ArrowRight

  return (
    <section className="tool-panel" aria-labelledby="detector-settings-title">
      <header className="tool-panel-header">
        <div>
          <h2 id="detector-settings-title" className="tool-panel-label">
            <Settings2 size={16} className="text-olive" aria-hidden="true" />
            Cài đặt nhận diện
          </h2>
          <p className="tool-panel-meta">Điều chỉnh mô hình và ngưỡng trước khi phân tích.</p>
        </div>
      </header>
      <div className="tool-panel-body">
        <div className="tool-field">
          <div className="tool-label-row">
            <label className="tool-label" htmlFor="model-mode">Mô hình</label>
          </div>
          <select
            id="model-mode"
            name="model_mode"
            className="tool-select"
            value={modelMode}
            disabled={loadingConfig || pending || disabled}
            onChange={(event) => onModelChange(event.target.value)}
          >
            {config.model_options.map((model) => (
              <option key={model.value} value={model.value} disabled={!model.available}>
                {getVietnameseModelLabel(model)}{model.available ? '' : ' — chưa khả dụng'}
              </option>
            ))}
          </select>
          {selectedModel?.warning ? (
            <p className="tool-model-warning">{getVietnameseModelWarning(selectedModel)}</p>
          ) : null}
        </div>

        <div className="tool-field">
          <div className="tool-label-row">
            <label className="tool-label" htmlFor="confidence-threshold">Ngưỡng tin cậy</label>
            <output className="tool-value" htmlFor="confidence-threshold">
              {Math.round(confidence * 100)}%
            </output>
          </div>
          <input
            id="confidence-threshold"
            name="conf_threshold"
            className="tool-range"
            type="range"
            min={config.confidence.min}
            max={config.confidence.max}
            step={config.confidence.step}
            value={confidence}
            disabled={loadingConfig || pending || disabled}
            onChange={(event) => onConfidenceChange(Number(event.target.value))}
          />
          <p className="tool-helper">
            Ngưỡng cao giảm cảnh báo nhầm nhưng có thể bỏ sót vật thể khó thấy.
          </p>
        </div>

        <button
          className="tool-primary-button"
          type="submit"
          disabled={loadingConfig || pending || disabled || !selectedModel?.available}
        >
          {pending ? pendingLabel : submitLabel}
          <SubmitIcon className={pending ? 'tool-spin-icon' : undefined} size={15} aria-hidden="true" />
        </button>
      </div>
    </section>
  )
}

export default DetectorSettings
