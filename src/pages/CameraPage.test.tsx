import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'

const testState = vi.hoisted(() => ({
  connectCamera: vi.fn(),
  releaseCameraConnection: vi.fn(() => Promise.resolve()),
  config: {
    ok: true as const,
    model_options: [
      {
        value: 'yolo11n_behavior_p2',
        label: 'Phone + Using Phone',
        available: false,
        warning: 'Không tìm thấy checkpoint Phone + Using Phone.',
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
    confidence: { min: 0.1, max: 0.9, step: 0.05 },
    upload: {
      max_bytes: 10_000_000,
      max_mb: 10,
      image: { extensions: ['.jpg'], mime_types: ['image/jpeg'] },
      video: { extensions: ['.mp4'], mime_types: ['video/mp4'] },
    },
  },
}))

vi.mock('../hooks/useApiConfig', () => ({
  useApiConfig: () => ({
    config: testState.config,
    loading: false,
    error: '',
  }),
}))

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    connectCamera: testState.connectCamera,
    releaseCameraConnection: testState.releaseCameraConnection,
  }
})

import CameraPage from './CameraPage'

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location-search">{location.search}</output>
}

beforeEach(() => {
  testState.connectCamera.mockReset()
  testState.releaseCameraConnection.mockClear()
})

afterEach(cleanup)

describe('camera model availability', () => {
  it('keeps an unavailable YOLO11n default selected without auto-connecting or switching to Phone', async () => {
    render(
      <MemoryRouter initialEntries={['/camera?model_mode=yolo12n_behavior_p2&conf_threshold=0.7']}>
        <CameraPage />
        <LocationProbe />
      </MemoryRouter>,
    )

    expect(screen.getByText('Không tìm thấy checkpoint Phone + Using Phone.')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Mô hình' })).toHaveValue('yolo11n_behavior_p2')
    expect(screen.getByRole('option', {
      name: 'Phone + Using Phone — chưa khả dụng',
    })).toBeDisabled()
    expect(screen.getByRole('option', { name: 'Phone' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Kiểm tra và kết nối' })).toBeDisabled()
    expect(screen.getByText('Bộ nhận diện chưa sẵn sàng')).toBeInTheDocument()
    expect(screen.getByText('AI đã tạm dừng')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId('location-search')).toHaveTextContent('model_mode=yolo11n_behavior_p2')
    })
    expect(screen.getByTestId('location-search')).toHaveTextContent('conf_threshold=0.7')
    expect(testState.connectCamera).not.toHaveBeenCalled()
  })
})
