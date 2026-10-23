import { ScanEye } from 'lucide-react'
import { Link } from 'react-router-dom'

const footerLinks = [
  { label: 'Trang chủ', to: '/' },
  { label: 'Ảnh', to: '/image' },
  { label: 'Video', to: '/video' },
  { label: 'Camera', to: '/camera' },
]

function Footer() {
  return (
    <footer className="border-t border-white/[0.08] bg-black px-6 py-8 md:py-10">
      <div className="section-shell grid gap-8 md:grid-cols-[1fr_auto] md:items-center">
        <div>
          <Link to="/" className="inline-flex items-center gap-2.5 text-sm font-semibold text-paper">
            <span className="grid size-8 place-items-center rounded-full bg-white/[0.05] text-olive">
              <ScanEye size={17} strokeWidth={1.7} aria-hidden="true" />
            </span>
            Giám sát thi cử AI
          </Link>
          <p className="mt-4 text-xs leading-5 text-paper/60">Gợi ý từ AI luôn cần con người xem xét.</p>
        </div>
        <nav className="flex flex-wrap items-center gap-x-6 gap-y-3" aria-label="Điều hướng chân trang">
          {footerLinks.map((item) => (
            <Link key={item.label} to={item.to} className="text-xs font-medium text-paper/60 transition-colors hover:text-paper">
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="section-shell mt-8 border-t border-white/[0.06] pt-5 text-[11px] text-paper/60">
        © 2026 Giám sát thi cử AI
      </div>
    </footer>
  )
}

export default Footer
