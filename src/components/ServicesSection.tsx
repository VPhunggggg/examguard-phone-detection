import { motion, useReducedMotion } from 'framer-motion'
import { ArrowUpRight, Camera, Images } from 'lucide-react'
import { Link } from 'react-router-dom'
import CameraScanLoop from './CameraScanLoop'
import PhoneDetectionPreview from './PhoneDetectionPreview'

function ServicesSection() {
  const reduceMotion = useReducedMotion()

  return (
    <section id="image" className="relative overflow-hidden bg-black px-6 py-28 md:py-40">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,255,255,0.025)_0%,transparent_60%)]" />
      <div className="section-shell relative z-10">
        <div className="mb-12 flex items-end justify-between gap-6 md:mb-16">
          <h2 className="vietnamese-heading text-[clamp(3rem,6vw,5.25rem)] leading-[1.08] text-paper">Hệ thống làm được gì</h2>
          <span className="hidden pb-2 text-xs font-semibold text-paper/60 sm:block">Tính năng chính</span>
        </div>

        <div className="grid gap-6 md:grid-cols-[1.08fr_.92fr] md:gap-8">
          <motion.article
            className="liquid-glass group overflow-hidden rounded-[24px]"
            initial={reduceMotion ? undefined : { y: 30, opacity: 0.76 }}
            whileInView={{ y: 0, opacity: 1 }}
            viewport={{ once: true, amount: 0.2 }}
            whileHover={reduceMotion ? undefined : { y: -5 }}
            transition={{ duration: 0.72, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="relative z-[1]">
              <PhoneDetectionPreview className="min-h-[350px] md:min-h-[390px]" />
              <div className="p-6 md:p-8">
                <div className="flex items-center justify-between gap-4">
                  <span className="flex items-center gap-2 text-xs font-semibold text-olive"><Images size={15} aria-hidden="true" /> Ảnh và video</span>
                  <Link to="/image" className="grid size-9 place-items-center rounded-full bg-white/[0.05] text-paper/55 transition-colors group-hover:bg-paper group-hover:text-ink" aria-label="Mở phân tích ảnh">
                    <ArrowUpRight size={15} aria-hidden="true" />
                  </Link>
                </div>
                <h3 className="vietnamese-heading mt-5 text-4xl leading-[1.12] text-paper md:text-5xl">Phát hiện điện thoại trong ảnh và video</h3>
                <p className="mt-4 max-w-xl text-sm leading-6 text-paper/55 md:text-base md:leading-7">Phân tích ảnh và video đã tải lên, sau đó trả về kết quả được chú thích bằng khung nhận diện và độ tin cậy.</p>
              </div>
            </div>
          </motion.article>

          <motion.article
            id="camera"
            className="liquid-glass group overflow-hidden rounded-[24px] md:mt-14"
            initial={reduceMotion ? undefined : { y: 38, opacity: 0.76 }}
            whileInView={{ y: 0, opacity: 1 }}
            viewport={{ once: true, amount: 0.2 }}
            whileHover={reduceMotion ? undefined : { y: -5 }}
            transition={{ duration: 0.76, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="relative z-[1]">
              <CameraScanLoop compact className="min-h-[330px] md:min-h-[350px]" />
              <div className="p-6 md:p-8">
                <div className="flex items-center justify-between gap-4">
                  <span className="flex items-center gap-2 text-xs font-semibold text-cyan"><Camera size={15} aria-hidden="true" /> Camera trực tiếp</span>
                  <Link to="/camera" className="grid size-9 place-items-center rounded-full bg-white/[0.05] text-paper/55 transition-colors group-hover:bg-paper group-hover:text-ink" aria-label="Mở giám sát camera">
                    <ArrowUpRight size={15} aria-hidden="true" />
                  </Link>
                </div>
                <h3 className="vietnamese-heading mt-5 text-4xl leading-[1.12] text-paper md:text-5xl">Giám sát kỳ thi theo thời gian thực</h3>
                <p className="mt-4 max-w-lg text-sm leading-6 text-paper/55 md:text-base md:leading-7">Sử dụng luồng camera trực tiếp để nhận diện hoạt động điện thoại đáng ngờ và thông báo cho giáo viên khi cần chú ý.</p>
              </div>
            </div>
          </motion.article>
        </div>
      </div>
    </section>
  )
}

export default ServicesSection
