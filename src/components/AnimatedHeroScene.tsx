import { motion, useReducedMotion } from 'framer-motion'
import heroExamHall from '../assets/generated/hero-exam-hall-v2.webp'

const particles = [
  ['11%', '24%', 0],
  ['18%', '68%', 1.4],
  ['29%', '38%', 2.8],
  ['36%', '77%', 0.7],
  ['47%', '19%', 3.2],
  ['56%', '61%', 1.8],
  ['64%', '31%', 0.4],
  ['72%', '72%', 2.2],
  ['81%', '24%', 1.1],
  ['89%', '58%', 3.5],
] as const

function AnimatedHeroScene() {
  const reduceMotion = useReducedMotion()

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <motion.img
        src={heroExamHall}
        alt=""
        loading="eager"
        decoding="async"
        className="absolute inset-0 h-full w-full object-cover object-center opacity-70 [filter:saturate(.72)_contrast(1.06)_brightness(.76)]"
        animate={reduceMotion ? undefined : { scale: [1, 1.025, 1] }}
        transition={{ duration: 20, ease: 'easeInOut', repeat: Infinity }}
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(2,4,3,0.32)_0%,rgba(2,4,3,0.08)_36%,rgba(2,4,3,0.58)_78%,#020403_100%)]" />

      <motion.div
        className="hero-light-field"
        animate={
          reduceMotion
            ? undefined
            : { x: ['-1%', '2%', '-1%'], y: ['1%', '-2%', '1%'], scale: [1, 1.04, 1] }
        }
        transition={{ duration: 18, ease: 'easeInOut', repeat: Infinity }}
      />
      <div className="scan-grid" />

      <motion.div
        className="absolute left-[69.2%] top-[76%] hidden h-[8.5%] w-[4.2%] min-w-12 text-alert md:block"
        animate={reduceMotion ? undefined : { opacity: [0.45, 0.9, 0.45] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
      >
        <span className="corner-mark absolute inset-0 border border-alert/45" />
      </motion.div>

      <motion.div
        className="absolute inset-x-[8%] top-[62%] h-px bg-gradient-to-r from-transparent via-cyan/50 to-transparent shadow-[0_0_24px_rgba(141,217,208,0.28)]"
        animate={reduceMotion ? undefined : { y: [-120, 150, -120], opacity: [0, 0.7, 0] }}
        transition={{ duration: 8, ease: 'easeInOut', repeat: Infinity }}
      />

      {particles.map(([left, top, delay], index) => (
        <motion.span
          key={`${left}-${top}`}
          className={`absolute rounded-full ${index % 3 === 0 ? 'size-1 bg-cyan/70' : 'size-0.5 bg-olive/60'}`}
          style={{ left, top }}
          animate={
            reduceMotion
              ? undefined
              : { y: [0, -18, 0], x: [0, index % 2 ? 7 : -7, 0], opacity: [0.2, 0.85, 0.2] }
          }
          transition={{ duration: 5 + (index % 3), delay, repeat: Infinity, ease: 'easeInOut' }}
        />
      ))}

      <div className="hero-vignette" />
    </div>
  )
}

export default AnimatedHeroScene
