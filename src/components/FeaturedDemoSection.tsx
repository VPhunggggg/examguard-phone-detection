import { motion, useReducedMotion } from 'framer-motion'
import { ArrowUpRight } from 'lucide-react'
import DetectionVideoMockup from './DetectionVideoMockup'
import LiquidButton from './LiquidButton'

function FeaturedDemoSection() {
  const reduceMotion = useReducedMotion()

  return (
    <section id="video" className="bg-black px-6 pb-24 pt-8 md:pb-32 md:pt-12">
      <motion.div
        className="relative mx-auto max-w-6xl overflow-hidden rounded-[24px] bg-[#050806] shadow-[0_34px_120px_rgba(0,0,0,0.46)]"
        initial={reduceMotion ? undefined : { y: 28, scale: 0.985 }}
        whileInView={{ y: 0, scale: 1 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
      >
        <DetectionVideoMockup />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 h-[62%] bg-gradient-to-t from-black via-black/65 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 z-30 flex flex-col items-start justify-between gap-5 p-4 sm:p-6 md:flex-row md:items-end md:p-10">
          <div className="liquid-glass pointer-events-auto max-w-lg rounded-2xl p-5 md:p-7">
            <div className="relative z-[1]">
              <span className="text-xs font-semibold text-olive">Phát hiện trực tiếp bằng AI</span>
              <p className="mt-3 text-sm leading-6 text-paper/65 md:text-base md:leading-7">
                Tải ảnh lên, xử lý video hoặc theo dõi luồng camera. Hệ thống làm nổi bật khả năng sử dụng điện thoại bằng khung nhận diện, độ tin cậy và bằng chứng sẵn sàng để rà soát.
              </p>
            </div>
          </div>
          <LiquidButton
            href="/camera"
            className="pointer-events-auto shrink-0 bg-black/20"
            icon={<ArrowUpRight size={16} aria-hidden="true" />}
          >
            Khám phá tính năng giám sát
          </LiquidButton>
        </div>
      </motion.div>
    </section>
  )
}

export default FeaturedDemoSection
