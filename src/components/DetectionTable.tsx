import type { Detection } from '../api/client'
import { getVietnameseDetectionLabel } from '../utils/vietnamese'

type DetectionTableProps = {
  detections: Detection[]
}

function getDetectionClassLabel(detection: Detection): string {
  if (detection.class_id === 1) return 'Phone · Class 1'
  if (detection.class_id === 7) return 'Using Phone · Class 7'
  return detection.is_phone ? `Phone · Class ${detection.class_id}` : 'Vật thể khác'
}

function isPhoneDetection(detection: Detection): boolean {
  return detection.is_phone || detection.class_id === 1 || detection.class_id === 7
}

function DetectionTable({ detections }: DetectionTableProps) {
  if (!detections.length) {
    return (
      <div className="tool-empty-result" role="status">
        Không có vật thể nào vượt qua ngưỡng tin cậy đã chọn.
      </div>
    )
  }

  return (
    <div className="tool-table-wrap" tabIndex={0} aria-label="Bảng chi tiết kết quả nhận diện">
      <table className="tool-table">
        <caption className="sr-only">Danh sách vật thể được mô hình phát hiện</caption>
        <thead>
          <tr>
            <th scope="col">Nhãn</th>
            <th scope="col">Độ tin cậy</th>
            <th scope="col">Mã lớp</th>
            <th scope="col">Phân loại</th>
            <th scope="col">Tọa độ khung nhận diện</th>
          </tr>
        </thead>
        <tbody>
          {detections.map((detection, index) => (
            <tr key={`${detection.class_id}-${detection.x1}-${detection.y1}-${index}`}>
              <td>{getVietnameseDetectionLabel(detection.label)}</td>
              <td>{(detection.confidence * 100).toFixed(1)}%</td>
              <td>{detection.class_id}</td>
              <td>
                <span className="tool-pill" data-alert={isPhoneDetection(detection)}>
                  {getDetectionClassLabel(detection)}
                </span>
              </td>
              <td>
                {Math.round(detection.x1)}, {Math.round(detection.y1)} → {Math.round(detection.x2)}, {Math.round(detection.y2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default DetectionTable
