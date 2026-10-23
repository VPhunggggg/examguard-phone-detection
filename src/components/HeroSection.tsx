import { motion, useReducedMotion } from 'framer-motion'
import {
  ArrowRight,
  FileCheck2,
  Play,
  RadioTower,
  Send,
  ShieldCheck,
  Smartphone,
  UsersRound,
} from 'lucide-react'
import AnimatedHeroScene from './AnimatedHeroScene'
import LiquidButton from './LiquidButton'

const floatingPanels = [
  {
    title: 'Phát hiện điện thoại',
    detail: 'Độ tin cậy 92%',
    icon: Smartphone,
    accent: 'text-alert',
    position: 'left-[5%] top-[42%]',
    delay: 0,
  },
  {
    title: 'Phòng A-302',
    detail: 'Đang giám sát',
    icon: RadioTower,
    accent: 'text-cyan',
    position: 'right-[5%] top-[35%]',
    delay: 0.8,
  },
  {
    title: 'Đã quét 32 thí sinh',
    detail: 'Rà soát liên tục',
    icon: UsersRound,
    accent: 'text-olive',
    position: 'left-[9%] bottom-[18%]',
    delay: 1.4,
  },
  {
    title: 'Đã lưu bằng chứng',
    detail: 'Khung hình · 09:42:18',
    icon: FileCheck2,
    accent: 'text-olive',
    position: 'right-[8%] bottom-[19%]',
    delay: 2,
  },
]

const trustItems = ['Phát hiện theo thời gian thực', 'Bảo vệ quyền riêng tư', 'Thiết kế cho trường học']

function HeroSection() {
  const reduceMotion = useReducedMotion()

  return (
    <section id="home" className="relative flex min-h-[100svh] flex-col overflow-hidden bg-black">
      <AnimatedHeroScene />
      {floatingPanels.map((panel) => {
        const Icon = panel.icon
        return (
          <motion.div
            key={panel.title}
            className={`liquid-glass absolute z-20 hidden min-w-48 rounded-xl px-4 py-3 xl:block ${panel.position}`}
            animate={reduceMotion ? undefined : { y: [0, -8, 0], rotate: [0, 0.35, 0] }}
            transition={{ duration: 5.4, delay: panel.delay, ease: 'easeInOut', repeat: Infinity }}
          >
            <div className="relative z-[1] flex items-center gap-3">
              <span className={`grid size-9 place-items-center rounded-full bg-white/[0.055] ${panel.accent}`}>
                <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
              </span>
              <span>
                <strong className="block text-xs font-semibold text-paper">{panel.title}</strong>
                <small className="mt-1 block text-[10px] text-paper/60">{panel.detail}</small>
              </span>
            </div>
          </motion.div>
        )
      })}

      <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-5 pb-10 pt-16 text-center sm:px-6 lg:-translate-y-4 lg:pb-14">
        <motion.div
          className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/[0.035] px-3 py-1.5 text-[11px] font-semibold text-paper/60"
          initial={reduceMotion ? undefined : { opacity: 0.72, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="pulse-dot size-1.5 rounded-full bg-olive" />
          AI hỗ trợ rà soát bằng chứng
        </motion.div>

        <motion.h1
          className="vietnamese-heading max-w-5xl text-[clamp(3.05rem,7.4vw,5.75rem)] leading-[1.08] text-paper"
          initial={reduceMotion ? undefined : { y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
        >
          Giám sát thi cử bằng <em className="not-italic text-olive">AI</em>
        </motion.h1>

        <motion.p
          className="mt-6 max-w-2xl text-base leading-7 text-paper/62 sm:text-lg sm:leading-8"
          initial={reduceMotion ? undefined : { y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.22, ease: [0.16, 1, 0.3, 1] }}
        >
          Phát hiện hành vi sử dụng điện thoại trong ảnh, video và camera trực tiếp.
          Giữ mọi cảnh báo rõ ràng để giám thị là người đưa ra quyết định cuối cùng.
        </motion.p>

        <motion.div
          className="mt-8 flex w-full flex-col items-center justify-center gap-3 sm:w-auto sm:flex-row"
          initial={reduceMotion ? undefined : { y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.75, delay: 0.34, ease: [0.16, 1, 0.3, 1] }}
        >
          <LiquidButton
            href="/image"
            className="w-full bg-white/[0.035] sm:w-auto"
            icon={<ArrowRight size={16} aria-hidden="true" />}
          >
            Bắt đầu phân tích
          </LiquidButton>
          <LiquidButton
            href="#video"
            variant="text"
            className="w-full sm:w-auto"
            icon={<Play size={14} fill="currentColor" aria-hidden="true" />}
          >
            Xem mô phỏng
          </LiquidButton>
        </motion.div>

        <motion.a
          href="https://t.me/ai_exam_monitoring_2026_bot"
          target="_blank"
          rel="noopener noreferrer"
          className="liquid-glass group mt-7 flex min-h-[52px] w-full max-w-md items-center justify-between rounded-full p-1.5 pl-5 text-sm font-semibold text-paper transition-colors duration-200 hover:bg-white/[0.06]"
          initial={reduceMotion ? undefined : { y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.75, delay: 0.44, ease: [0.16, 1, 0.3, 1] }}
          whileHover={reduceMotion ? undefined : { y: -2, scale: 1.01 }}
          whileTap={reduceMotion ? undefined : { scale: 0.98 }}
        >
          <span className="relative z-[1] min-w-0 flex-1 text-left">
            Nhận thông báo gian lận qua Telegram
          </span>
          <span className="relative z-[1] grid size-10 shrink-0 place-items-center rounded-full bg-paper text-ink transition-colors duration-200 group-hover:bg-olive">
            <Send size={17} aria-hidden="true" />
          </span>
        </motion.a>
        <p className="mt-2 min-h-5 text-[11px] text-paper/70">
          Mở bot và nhấn Bắt đầu để đăng ký nhận cảnh báo.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-2 sm:mt-10">
          {trustItems.map((item) => (
            <span key={item} className="liquid-glass rounded-full px-3 py-2 text-[10px] font-semibold text-paper/55 sm:px-4 sm:text-[11px]">
              <span className="relative z-[1] flex items-center gap-2"><ShieldCheck size={12} className="text-olive" aria-hidden="true" />{item}</span>
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

export default HeroSection
