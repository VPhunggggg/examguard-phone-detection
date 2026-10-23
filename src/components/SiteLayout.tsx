import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import CanvasCursor from './CanvasCursor'
import Footer from './Footer'
import Navbar from './Navbar'
import ScrollManager from './ScrollManager'

function SiteLayout() {
  return (
    <div className="min-h-screen overflow-x-clip bg-ink text-paper selection:bg-olive selection:text-ink">
      <a className="skip-link" href="#main-content">Bỏ qua điều hướng</a>
      <CanvasCursor />
      <ScrollManager />
      <Navbar />
      <div id="main-content" tabIndex={-1}>
        <Suspense fallback={<div className="app-loading" role="status">Đang tải giao diện…</div>}>
          <Outlet />
        </Suspense>
      </div>
      <Footer />
    </div>
  )
}

export default SiteLayout
