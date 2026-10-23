import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getErrorMessage, type ApiConfig } from '../api/client'
import { getVietnameseModelLabel, getVietnameseModelValueLabel } from '../utils/vietnamese'
import DetectionTable from './DetectionTable'
import DetectorSettings from './DetectorSettings'

afterEach(cleanup)

const CONFIG: ApiConfig = {
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
    model_mode: 'yolo11n_behavior_p2',
    conf_threshold: 0.5,
  },
  confidence: { min: 0.1, max: 0.9, step: 0.05 },
  upload: {
    max_bytes: 10_000_000,
    max_mb: 10,
    image: { extensions: ['.jpg'], mime_types: ['image/jpeg'] },
    video: { extensions: ['.mp4'], mime_types: ['video/mp4'] },
  },
}

describe('Việt hóa giao diện công cụ', () => {
  it('chỉ hiển thị hai model công khai và giữ nguyên giá trị canonical gửi API', () => {
    render(
      <DetectorSettings
        config={CONFIG}
        modelMode={CONFIG.defaults.model_mode}
        confidence={0.5}
        submitLabel="Phân tích"
        onModelChange={vi.fn()}
        onConfidenceChange={vi.fn()}
      />,
    )

    expect(screen.getByRole('option', {
      name: 'Phone + Using Phone',
    })).toHaveValue('yolo11n_behavior_p2')
    expect(screen.getByRole('option', {
      name: 'Phone',
    })).toHaveValue('yolov8n_coco_phone')
    expect(screen.getAllByRole('option')).toHaveLength(2)
    expect(getVietnameseModelValueLabel('yolo11n_behavior_p2')).toBe('Phone + Using Phone')
    expect(getVietnameseModelValueLabel('yolov8n_coco_phone')).toBe('Phone')
  })

  it('không còn ánh xạ nhãn thân thiện cho model đã gỡ', () => {
    expect(getVietnameseModelValueLabel('model_manh_nhat')).toBe('model_manh_nhat')
    expect(getVietnameseModelValueLabel('examguard_vision_system')).toBe('examguard_vision_system')
    expect(getVietnameseModelValueLabel('yolo12n_behavior_p2')).toBe('yolo12n_behavior_p2')
    expect(getVietnameseModelLabel({
      value: 'another_model',
      label: 'YOLO tùy chỉnh',
    })).toBe('YOLO tùy chỉnh')
  })

  it('vô hiệu hóa riêng model chưa khả dụng và hiển thị cảnh báo của model đó', () => {
    const unavailableConfig: ApiConfig = {
      ...CONFIG,
      model_options: CONFIG.model_options.map((model) => (
        model.value === 'yolov8n_coco_phone'
          ? { ...model, available: false, warning: 'Không tìm thấy checkpoint Phone.' }
          : model
      )),
    }

    render(
      <DetectorSettings
        config={unavailableConfig}
        modelMode="yolov8n_coco_phone"
        confidence={0.5}
        submitLabel="Phân tích"
        onModelChange={vi.fn()}
        onConfidenceChange={vi.fn()}
      />,
    )

    expect(screen.getByRole('option', {
      name: 'Phone — chưa khả dụng',
    })).toBeDisabled()
    expect(screen.getByText('Không tìm thấy checkpoint Phone.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Phân tích' })).toBeDisabled()
  })

  it('Việt hóa riêng hai class điện thoại và đánh dấu cả hai là cảnh báo điện thoại', () => {
    render(<DetectionTable detections={[
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
    ]} />)

    expect(screen.getByText('Điện thoại')).toBeInTheDocument()
    expect(screen.getByText('Đang sử dụng điện thoại')).toBeInTheDocument()
    expect(screen.getByText('Phone · Class 1')).toHaveAttribute('data-alert', 'true')
    expect(screen.getByText('Using Phone · Class 7')).toHaveAttribute('data-alert', 'true')
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Mã lớp' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Tọa độ khung nhận diện' })).toBeInTheDocument()
  })

  it('hiển thị Class 7 là Using Phone và vẫn kích hoạt trạng thái cảnh báo', () => {
    render(<DetectionTable detections={[
      {
        label: 'using_phone',
        confidence: 0.88,
        class_id: 7,
        is_phone: true,
        x1: 24,
        y1: 30,
        x2: 128,
        y2: 192,
      },
    ]} />)

    expect(screen.getByText('Đang sử dụng điện thoại')).toBeInTheDocument()
    expect(screen.getByText('Using Phone · Class 7')).toHaveAttribute('data-alert', 'true')
    expect(screen.queryByText('Phone · Class 1')).not.toBeInTheDocument()
  })

  it('không hiển thị thông báo lỗi tiếng Anh từ API', () => {
    expect(getErrorMessage(new ApiError(429, {
      code: 'rate_limited',
      message: 'Too many requests',
      retry_after_seconds: 12,
    }))).toBe('Có quá nhiều yêu cầu. Vui lòng thử lại sau 12 giây.')

    expect(getErrorMessage(new ApiError(503, {
      code: 'detector_unavailable',
      message: 'Model is unavailable',
    }))).toBe('Bộ nhận diện đã chọn hiện chưa sẵn sàng. Hãy kiểm tra tệp model rồi thử lại.')
  })
})
