import {
  motion,
  type MotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from 'framer-motion'
import { useRef } from 'react'

const aboutHeading = 'Được xây dựng cho kỳ thi công bằng hơn, giám sát thông minh hơn và rà soát bằng chứng nhanh hơn.'

type HeadingPhrase = {
  text: string
  range: [number, number]
}

const headingPhrases: HeadingPhrase[] = [
  { text: 'Được xây dựng cho kỳ thi ', range: [0, 0.2] },
  { text: 'công bằng hơn, ', range: [0.12, 0.32] },
  { text: 'giám sát ', range: [0.24, 0.44] },
  { text: 'thông minh hơn ', range: [0.36, 0.56] },
  { text: 'và rà soát ', range: [0.48, 0.68] },
  { text: 'bằng chứng nhanh hơn.', range: [0.54, 0.7] },
]

type RevealPhraseProps = {
  progress: MotionValue<number>
  range: [number, number]
  reducedMotion: boolean
  children: string
}

function RevealPhrase({ progress, range, reducedMotion, children }: RevealPhraseProps) {
  const opacity = useTransform(progress, range, [0.42, 1])

  return (
    <motion.span
      aria-hidden="true"
      data-reveal-phrase="true"
      style={{ opacity: reducedMotion ? 1 : opacity }}
    >
      {children}
    </motion.span>
  )
}

function AboutSection() {
  const reduceMotion = useReducedMotion()
  const sectionRef = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start 82%', 'end 45%'],
  })
  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 125,
    damping: 30,
    mass: 0.28,
    restDelta: 0.001,
  })

  return (
    <section
      ref={sectionRef}
      id="about"
      className="relative overflow-hidden bg-black px-6 pb-14 pt-32 md:pb-20 md:pt-44"
    >
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.035)_0%,transparent_68%)]" />
      <motion.div
        className="section-shell relative z-10"
        initial={reduceMotion ? undefined : { y: 34, opacity: 0.72 }}
        whileInView={{ y: 0, opacity: 1 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.85, ease: [0.16, 1, 0.3, 1] }}
      >
        <span className="meta-label">Về hệ thống</span>
        <h2
          aria-label={aboutHeading}
          data-scroll-reveal="phrases"
          className="vietnamese-heading mt-8 max-w-5xl text-[clamp(2.75rem,6.8vw,5.6rem)] leading-[1.08] text-paper"
        >
          {headingPhrases.map((phrase) => (
            <RevealPhrase
              key={phrase.text}
              progress={smoothProgress}
              range={phrase.range}
              reducedMotion={Boolean(reduceMotion)}
            >
              {phrase.text}
            </RevealPhrase>
          ))}
        </h2>
        <div className="mt-10 flex justify-end md:mt-14">
          <p className="max-w-xl text-base leading-7 text-paper/58 md:text-lg md:leading-8">
            Hệ thống giám sát thi cử AI giúp giáo viên phát hiện việc sử dụng điện thoại và hành vi đáng ngờ mà không thay thế phán đoán của con người. Hệ thống làm nổi bật những tình huống cần chú ý để giám thị xem xét và đưa ra quyết định.
          </p>
        </div>
      </motion.div>
    </section>
  )
}

export default AboutSection
