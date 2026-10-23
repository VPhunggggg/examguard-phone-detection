import { motion, useReducedMotion } from 'framer-motion'
import { FileImage, ScanSearch } from 'lucide-react'
import phoneEvidence from '../assets/generated/phone-evidence-v2.webp'

type PhoneDetectionPreviewProps = {
  className?: string
}

function PhoneDetectionPreview({ className = '' }: PhoneDetectionPreviewProps) {
  const reduceMotion = useReducedMotion()

  return (
    <div
      className={`relative h-full min-h-[310px] overflow-hidden bg-[#080b08] ${className}`}
      aria-label="Mô phỏng phân tích ảnh có điện thoại trên bàn thi"
    >
      <motion.img
        src={phoneEvidence}
        alt=""
        loading="lazy"
        decoding="async"
        className="absolute inset-0 h-full w-full object-cover object-center [filter:saturate(.78)_contrast(1.03)_brightness(.78)]"
        animate={reduceMotion ? undefined : { scale: [1, 1.015, 1] }}
        transition={{ duration: 13, repeat: Infinity, ease: 'easeInOut' }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_62%_48%,transparent_18%,rgba(2,4,3,0.1)_58%,rgba(2,4,3,0.46)_100%)]" />

      <motion.div
        className="absolute left-[64%] top-[28%] h-[43%] w-[27%] min-w-[70px] text-alert sm:left-[60%] sm:top-[20%] sm:h-[56%] sm:w-[18.5%]"
        initial={{ opacity: 0.5, scale: 0.96 }}
        animate={
          reduceMotion
            ? { opacity: 1, scale: 1 }
            : { opacity: [0.5, 1, 1, 0.5], scale: [0.96, 1, 1, 0.96] }
        }
        transition={{ duration: 4, repeat: Infinity, times: [0, 0.18, 0.82, 1] }}
      >
        <span className="corner-mark absolute inset-0 border border-alert/60" />
        <span className="absolute -top-7 right-0 whitespace-nowrap rounded-sm bg-alert px-2 py-1 text-[9px] font-bold uppercase tracking-[0.08em] text-[#140806]">
          ĐIỆN THOẠI · 92%
        </span>
      </motion.div>

      <motion.div
        className="media-scanline"
        animate={reduceMotion ? undefined : { top: ['10%', '90%', '10%'] }}
        transition={{ duration: 5.8, ease: 'easeInOut', repeat: Infinity }}
      />

      <div className="absolute left-4 top-4 z-20 flex items-center gap-2 rounded-full bg-black/60 px-3 py-2 text-[10px] font-semibold text-paper/70">
        <FileImage size={13} className="text-olive" aria-hidden="true" /> IMG_2048.JPG
      </div>
      <div className="liquid-glass absolute bottom-4 right-4 z-20 rounded-full px-3 py-2">
        <span className="relative z-[1] flex items-center gap-2 text-[10px] font-semibold text-paper/70">
          <ScanSearch size={13} className="text-olive" aria-hidden="true" /> Phân tích hoàn tất
        </span>
      </div>
    </div>
  )
}

export default PhoneDetectionPreview
