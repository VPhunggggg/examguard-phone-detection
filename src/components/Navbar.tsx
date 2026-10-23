import { ArrowUpRight, Menu, ScanEye, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'

const navItems = [
  { label: 'Trang chủ', to: '/' },
  { label: 'Ảnh', to: '/image' },
  { label: 'Video', to: '/video' },
  { label: 'Camera', to: '/camera' },
]

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-3 py-2 text-[13px] font-medium transition-colors ${
    isActive ? 'bg-white/[0.065] text-paper' : 'text-paper/55 hover:text-paper'
  }`

function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname, location.hash])

  useEffect(() => {
    if (!menuOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [menuOpen])

  return (
    <header className="site-header fixed inset-x-0 top-0 z-[var(--z-nav)] px-4 pt-4 sm:px-6 sm:pt-6">
      <div className="relative mx-auto max-w-[1180px]">
        <nav
          className="liquid-glass flex min-h-14 items-center justify-between rounded-full px-3 py-2 sm:px-5"
          aria-label="Điều hướng chính"
        >
          <Link
            to="/"
            className="relative z-[1] flex min-w-0 items-center gap-2.5 rounded-full px-2 text-sm font-semibold text-paper"
            aria-label="Giám sát thi cử AI — Trang chủ"
          >
            <span className="grid size-8 shrink-0 place-items-center rounded-full bg-white/[0.07] text-olive">
              <ScanEye size={19} strokeWidth={1.7} aria-hidden="true" />
            </span>
            <span className="hidden whitespace-nowrap min-[480px]:inline">Giám sát thi cử AI</span>
          </Link>

          <div className="relative z-[1] hidden items-center gap-1 lg:flex">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === '/'} className={navClass}>
                {item.label}
              </NavLink>
            ))}
            <Link
              to="/#report"
              className="rounded-full px-3 py-2 text-[13px] font-medium text-paper/55 transition-colors hover:text-paper"
            >
              Báo cáo
            </Link>
          </div>

          <div className="relative z-[1] flex items-center gap-1 sm:gap-2">
            <Link
              to="/#about"
              className="hidden rounded-full px-3 py-2 text-xs font-semibold text-paper/60 transition-colors hover:text-paper sm:inline-flex"
            >
              Tìm hiểu
            </Link>
            <Link className="site-nav-cta" to="/image">
              Kiểm tra ngay <ArrowUpRight size={15} aria-hidden="true" />
            </Link>
            <button
              className="site-menu-trigger lg:hidden"
              type="button"
              aria-label={menuOpen ? 'Đóng menu' : 'Mở menu'}
              aria-expanded={menuOpen}
              aria-controls="mobile-navigation"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? <X size={19} aria-hidden="true" /> : <Menu size={19} aria-hidden="true" />}
            </button>
          </div>
        </nav>

        {menuOpen ? (
          <nav id="mobile-navigation" className="site-mobile-menu liquid-glass" aria-label="Điều hướng di động">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === '/'} className={navClass}>
                {item.label}
              </NavLink>
            ))}
            <Link to="/#report" className="rounded-full px-3 py-2 text-[13px] font-medium text-paper/65">
              Báo cáo
            </Link>
          </nav>
        ) : null}
      </div>
    </header>
  )
}

export default Navbar
