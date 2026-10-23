import { motion, useReducedMotion } from 'framer-motion'
import { Camera, Radio, ScanLine } from 'lucide-react'
import fairnessExamRoom from '../assets/generated/fairness-exam-room-v2.webp'

type CameraScanLoopProps = {
  compact?: boolean
  className?: string
}

function CameraScanLoop({ compact = false, className = '' }: CameraScanLoopProps) {
  const reduceMotion = useReducedMotion()

  return (
    <div
      className={`monitoring-raster relative h-full min-h-[310px] overflow-hidden bg-[#060a07] ${className}`}
      aria-label="Mô phỏng camera quét phòng thi theo thời gian thực"
    >
      <motion.img
        src={fairnessExamRoom}
        alt=""
        loading="lazy"
        decoding="async"
        className="absolute inset-0 h-full w-full object-cover object-center [filter:saturate(.72)_contrast(1.03)_brightness(.68)]"
        animate={reduceMotion ? undefined : { scale: [1, 1.018, 1] }}
        transition={{ duration: 15, ease: 'easeInOut', repeat: Infinity }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_68%_38%,rgba(91,159,151,0.08),transparent_34%),linear-gradient(180deg,rgba(2,4,3,0.16),rgba(2,4,3,0.38))]" />

      <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between bg-black/35 px-4 py-3 text-[10px] font-semibold tracking-[0.09em] text-paper/60">
        <span className="flex items-center gap-2">
          <Camera size={13} aria-hidden="true" /> PHÒNG A-302
        </span>
        <span className="flex items-center gap-2 text-olive">
          <Radio size={12} aria-hidden="true" /> ĐANG GIÁM SÁT
        </span>
      </div>

      <motion.div
        className="absolute inset-y-0 z-10 w-[18%] bg-gradient-to-r from-transparent via-cyan/10 to-transparent"
        animate={reduceMotion ? undefined : { left: ['-20%', '102%', '-20%'] }}
        transition={{ duration: 7.5, ease: 'easeInOut', repeat: Infinity }}
      >
        <span className="absolute inset-y-0 left-1/2 w-px bg-cyan/55 shadow-[0_0_22px_rgba(141,217,208,0.35)]" />
      </motion.div>

      <motion.div
        className="absolute bottom-[18%] left-[43%] z-10 h-[30%] w-[18%] text-cyan"
        animate={reduceMotion ? undefined : { opacity: [0.35, 0.78, 0.35] }}
        transition={{ duration: 3.2, repeat: Infinity }}
      >
        <span className="corner-mark absolute inset-0" />
      </motion.div>

      {!compact ? (
        <div className="liquid-glass absolute bottom-4 left-4 right-4 z-20 rounded-xl px-4 py-3 sm:left-auto sm:w-60">
          <div className="relative z-[1] flex items-center gap-3">
            <span className="grid size-8 place-items-center rounded-full bg-cyan/10 text-cyan">
              <ScanLine size={15} aria-hidden="true" />
            </span>
            <span>
              <strong className="block text-xs font-semibold text-paper">Đã quét 32 thí sinh</strong>
              <small className="mt-0.5 block text-[10px] text-paper/60">Không có vi phạm · 09:42</small>
            </span>
          </div>
        </div>
      ) : (
        <div className="absolute bottom-4 left-4 z-20 flex items-center gap-2 rounded-full bg-black/60 px-3 py-2 text-[10px] font-semibold text-paper/70">
          <i className="pulse-dot size-1.5 rounded-full bg-cyan" /> Đang quét luồng trực tiếp
        </div>
      )}
    </div>
  )
}

export default CameraScanLoop
