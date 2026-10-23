import { motion, useReducedMotion } from 'framer-motion'
import { FileSearch2, UserCheck } from 'lucide-react'
import CameraScanLoop from './CameraScanLoop'

const principles = [
  {
    icon: UserCheck,
    label: 'Hỗ trợ giám thị',
    body: 'Hệ thống không thay thế giáo viên. Hệ thống giúp họ tập trung vào những thời điểm quan trọng bằng cách làm nổi bật nhanh chóng, rõ ràng các tình huống có dấu hiệu sử dụng điện thoại.',
  },
  {
    icon: FileSearch2,
    label: 'Rà soát dựa trên bằng chứng',
    body: 'Mỗi cảnh báo có thể kèm khung hình, dấu thời gian, độ tin cậy và khung nhận diện trực quan, nhờ đó quyết định cuối cùng luôn minh bạch và do con người đưa ra.',
  },
]

function PhilosophySection() {
  const reduceMotion = useReducedMotion()

  return (
    <section id="report" className="overflow-hidden bg-black px-6 py-28 md:py-40">
      <div className="section-shell">
        <motion.h2
          className="vietnamese-heading mb-16 text-[clamp(3.2rem,7.4vw,6rem)] leading-[1.08] text-paper md:mb-24"
          initial={reduceMotion ? undefined : { opacity: 0.7, x: -26 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.55 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          Công bằng <span className="text-paper/45">×</span> An toàn
        </motion.h2>

        <div className="grid items-stretch gap-10 lg:grid-cols-[1.08fr_.92fr] lg:gap-16">
          <motion.div
            className="liquid-glass min-h-[380px] overflow-hidden rounded-[24px]"
            initial={reduceMotion ? undefined : { clipPath: 'inset(0 0 12% 0)', y: 20 }}
            whileInView={{ clipPath: 'inset(0 0 0% 0)', y: 0 }}
            viewport={{ once: true, amount: 0.25 }}
            transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="relative z-[1] h-full">
              <CameraScanLoop />
            </div>
          </motion.div>

          <div className="flex flex-col justify-center">
            {principles.map((principle, index) => {
              const Icon = principle.icon
              return (
                <motion.article
                  key={principle.label}
                  className={`py-8 first:pt-0 last:pb-0 ${index > 0 ? 'border-t border-white/10' : ''}`}
                  initial={reduceMotion ? undefined : { opacity: 0.72, x: 22 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, amount: 0.45 }}
                  transition={{ duration: 0.65, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
                >
                  <div className="flex items-center gap-3">
                    <Icon size={18} strokeWidth={1.6} className="text-olive" aria-hidden="true" />
                    <h3 className="text-sm font-semibold text-paper">{principle.label}</h3>
                  </div>
                  <p className="mt-4 max-w-xl text-base leading-7 text-paper/56 md:text-lg md:leading-8">
                    {principle.body}
                  </p>
                </motion.article>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}

export default PhilosophySection
