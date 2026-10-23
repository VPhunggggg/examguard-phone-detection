import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, PlayCircle } from 'lucide-react'
import LiquidButton from './LiquidButton'

const particles = [
  { left: '8%', top: '28%', delay: 0 },
  { left: '17%', top: '70%', delay: 1.5 },
  { left: '29%', top: '16%', delay: 0.7 },
  { left: '43%', top: '76%', delay: 2.1 },
  { left: '58%', top: '20%', delay: 1.1 },
  { left: '72%', top: '68%', delay: 2.6 },
  { left: '84%', top: '26%', delay: 0.4 },
  { left: '92%', top: '62%', delay: 1.8 },
]

function FinalCTASection() {
  const reduceMotion = useReducedMotion()

  return (
    <section className="relative overflow-hidden bg-black px-6 py-28 text-center md:py-40">
      <div className="ambient-orb absolute left-1/2 top-1/2 h-[520px] w-[800px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(ellipse,rgba(112,154,98,0.16),transparent_66%)] blur-2xl" />
      {particles.map((particle, index) => (
        <motion.i
          key={`${particle.left}-${particle.top}`}
          className={`absolute rounded-full ${index % 3 === 0 ? 'size-1 bg-cyan/60' : 'size-0.5 bg-olive/50'}`}
          style={{ left: particle.left, top: particle.top }}
          animate={reduceMotion ? undefined : { y: [0, -16, 0], opacity: [0.2, 0.8, 0.2] }}
          transition={{ duration: 4.5 + (index % 3), delay: particle.delay, repeat: Infinity, ease: 'easeInOut' }}
          aria-hidden="true"
        />
      ))}

      <motion.div
        className="relative z-10 mx-auto max-w-5xl"
        initial={reduceMotion ? undefined : { opacity: 0.72, y: 28 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.35 }}
        transition={{ duration: 0.88, ease: [0.16, 1, 0.3, 1] }}
      >
        <h2 className="vietnamese-heading text-[clamp(3.25rem,7.2vw,6rem)] leading-[1.08] text-paper">Giúp mọi kỳ thi minh bạch hơn.</h2>
        <p className="mx-auto mt-7 max-w-2xl text-base leading-7 text-paper/56 md:text-lg md:leading-8">Bắt đầu với nhận diện ảnh, mở rộng sang phân tích video, rồi tiến tới giám sát camera theo thời gian thực.</p>
        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <LiquidButton href="/image" className="w-full bg-white/[0.035] sm:w-auto" icon={<ArrowRight size={16} aria-hidden="true" />}>Dùng thử hệ thống</LiquidButton>
          <LiquidButton href="#video" variant="text" className="w-full sm:w-auto" icon={<PlayCircle size={16} aria-hidden="true" />}>Xem quy trình hoạt động</LiquidButton>
        </div>
      </motion.div>
    </section>
  )
}

export default FinalCTASection
