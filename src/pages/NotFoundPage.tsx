import { ArrowLeft, SearchX } from 'lucide-react'
import { Link } from 'react-router-dom'

function NotFoundPage() {
  return (
    <main className="tool-page not-found-page">
      <div className="tool-shell not-found-shell">
        <span className="tool-empty-icon"><SearchX size={22} aria-hidden="true" /></span>
        <p className="tool-kicker not-found-kicker">404 · Không tìm thấy</p>
        <h1 className="tool-title">Không tìm thấy trang</h1>
        <p className="tool-description">
          Đường dẫn này không tồn tại trong ứng dụng. Hãy quay lại trang chủ hoặc chọn một công cụ trên thanh điều hướng.
        </p>
        <Link className="tool-home-link" to="/">
          <ArrowLeft size={15} aria-hidden="true" /> Về trang chủ
        </Link>
      </div>
    </main>
  )
}

export default NotFoundPage
