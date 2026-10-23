import type { ModelOption } from '../api/client'

const DETECTION_LABELS: Record<string, string> = {
  'cell phone': 'Điện thoại',
  cellphone: 'Điện thoại',
  phone: 'Điện thoại',
  using_phone: 'Đang sử dụng điện thoại',
  smartphone: 'Điện thoại',
  'mobile phone': 'Điện thoại',
  person: 'Người',
  book: 'Sách',
  laptop: 'Máy tính xách tay',
  tablet: 'Máy tính bảng',
}

export function getVietnameseModelLabel(option: Pick<ModelOption, 'value' | 'label'>): string {
  const normalizedValue = option.value.trim().toLocaleLowerCase('en-US')
  const normalizedLabel = option.label.trim().toLocaleLowerCase('vi')

  if (
    normalizedValue === 'yolo11n_behavior_p2'
    || normalizedLabel.includes('phone + using phone')
  ) {
    return 'Phone + Using Phone'
  }

  if (
    normalizedValue === 'yolov8n_coco_phone'
    || normalizedLabel === 'phone'
  ) {
    return 'Phone'
  }

  return option.label
}

export function getVietnameseModelValueLabel(value: string): string {
  return getVietnameseModelLabel({ value, label: value })
}

export function getVietnameseModelWarning(option: Pick<ModelOption, 'value' | 'warning'>): string {
  return option.warning
}

export function getVietnameseDetectionLabel(label: string): string {
  return DETECTION_LABELS[label.trim().toLocaleLowerCase('en-US')] ?? label
}
