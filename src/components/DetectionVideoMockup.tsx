import { motion, useReducedMotion } from 'framer-motion'
import { CircleDot, Clock3, Video } from 'lucide-react'
import liveDetectionRoom from '../assets/generated/live-detection-room-v2.webp'

const logItems = [
  { time: '09:42:18', label: 'Phát hiện điện thoại', alert: true },
  { time: '09:42:11', label: 'Đã rà soát khung hình', alert: false },
  { time: '09:41:52', label: 'Hoàn tất quét', alert: false },
]

function DetectionVideoMockup() {
  const reduceMotion = useReducedMotion()

  return (
    <div
      className="monitoring-raster relative min-h-[430px] overflow-hidden bg-[#050806] sm:min-h-[520px]"
      aria-label="Mô phỏng camera AI phát hiện điện thoại trong phòng thi"
    >
      <motion.img
        src={liveDetectionRoom}
        alt=""
        loading="lazy"
        decoding="async"
        className="absolute inset-0 h-full w-full object-cover object-[55%_center] [filter:saturate(.78)_contrast(1.04)_brightness(.82)]"
        animate={reduceMotion ? undefined : { scale: [1, 1.018, 1] }}
        transition={{ duration: 14, ease: 'easeInOut', repeat: Infinity }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_38%_42%,rgba(109,151,104,0.08),transparent_48%),linear-gradient(180deg,rgba(2,4,3,0.16),rgba(2,4,3,0.05)_52%,rgba(2,4,3,0.5))]" />

      <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between bg-black/45 px-4 py-3 text-[10px] font-semibold tracking-[0.08em] text-paper/60 sm:px-6 sm:text-xs">
        <span className="flex items-center gap-2">
          <Video size={14} className="text-cyan" aria-hidden="true" /> CAM 04 · PHÒNG A-302
        </span>
        <span className="flex items-center gap-2">
          <i className="pulse-dot size-1.5 rounded-full bg-alert" /> TRỰC TIẾP · 09:42:18
        </span>
      </div>

      <motion.div
        className="media-scanline"
        animate={reduceMotion ? undefined : { top: ['12%', '92%', '12%'] }}
        transition={{ duration: 6.8, ease: 'easeInOut', repeat: Infinity }}
      />

      <motion.div
        className="absolute left-[74%] top-[62%] z-10 h-[16%] w-[11%] min-w-[42px] text-alert sm:left-[64.5%] sm:top-[61.5%] sm:w-[6.2%]"
        animate={reduceMotion ? undefined : { opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 2.1, repeat: Infinity, ease: 'easeInOut' }}
      >
        <span className="corner-mark absolute inset-0 border border-alert/70" />
        <span className="absolute -top-7 right-0 whitespace-nowrap rounded-sm bg-alert px-2 py-1 text-[9px] font-bold uppercase tracking-[0.08em] text-[#140806] sm:text-[10px]">
          PHÁT HIỆN ĐIỆN THOẠI · 92%
        </span>
      </motion.div>

      <aside
        className="liquid-glass absolute right-4 top-16 z-20 hidden w-60 rounded-xl p-4 sm:block lg:right-6 lg:top-20"
        aria-label="Nhật ký phát hiện"
      >
        <div className="relative z-[1] flex items-center justify-between pb-3">
          <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-paper/60">Nhật ký phát hiện</span>
          <CircleDot size={14} className="text-olive" aria-hidden="true" />
        </div>
        <div className="relative z-[1] space-y-1">
          {logItems.map((item) => (
            <div
              key={item.time}
              className={`flex items-start gap-3 rounded-lg px-2.5 py-2.5 ${item.alert ? 'bg-alert/10' : 'bg-white/[0.025]'}`}
            >
              <span className={`mt-1 size-1.5 shrink-0 rounded-full ${item.alert ? 'bg-alert' : 'bg-paper/25'}`} />
              <span className="min-w-0 flex-1">
                <strong className={`block text-[11px] font-semibold ${item.alert ? 'text-paper' : 'text-paper/65'}`}>
                  {item.label}
                </strong>
                <small className="mt-1 block text-[9px] text-paper/60">{item.time}</small>
              </span>
            </div>
          ))}
        </div>
      </aside>

      <div className="absolute bottom-4 left-4 z-20 flex items-center gap-2 rounded-full bg-black/60 px-3 py-2 text-[10px] font-medium text-paper/70 sm:bottom-6 sm:left-6">
        <Clock3 size={12} className="text-olive" aria-hidden="true" />
        Khung hình bằng chứng · 00:14:22
      </div>
    </div>
  )
}

export default DetectionVideoMockup
