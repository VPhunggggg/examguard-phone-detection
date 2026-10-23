import { motion, useReducedMotion } from 'framer-motion'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

const MotionLink = motion.create(Link)

type LiquidButtonProps = {
  children: ReactNode
  href?: string
  variant?: 'glass' | 'light' | 'text'
  className?: string
  icon?: ReactNode
  ariaLabel?: string
}

const baseClass =
  'group relative inline-flex min-h-12 items-center justify-center gap-2 whitespace-nowrap rounded-full px-6 text-sm font-semibold transition-colors duration-200 focus-visible:outline-none'

function LiquidButton({
  children,
  href,
  variant = 'glass',
  className = '',
  icon,
  ariaLabel,
}: LiquidButtonProps) {
  const reduceMotion = useReducedMotion()
  const variantClass = {
    glass: 'liquid-glass text-paper hover:bg-white/[0.06]',
    light: 'bg-paper text-ink hover:bg-olive',
    text: 'text-paper/70 hover:text-paper',
  }[variant]
  const classes = `${baseClass} ${variantClass} ${className}`
  const motionProps = reduceMotion
    ? {}
    : { whileHover: { scale: 1.035 }, whileTap: { scale: 0.97 } }

  if (href) {
    if (href.startsWith('/')) {
      return (
        <MotionLink to={href} className={classes} aria-label={ariaLabel} {...motionProps}>
          <span className="relative z-[1]">{children}</span>
          {icon ? <span className="relative z-[1]">{icon}</span> : null}
        </MotionLink>
      )
    }

    return (
      <motion.a href={href} className={classes} aria-label={ariaLabel} {...motionProps}>
        <span className="relative z-[1]">{children}</span>
        {icon ? <span className="relative z-[1]">{icon}</span> : null}
      </motion.a>
    )
  }

  return (
    <motion.button type="button" className={classes} aria-label={ariaLabel} {...motionProps}>
      <span className="relative z-[1]">{children}</span>
      {icon ? <span className="relative z-[1]">{icon}</span> : null}
    </motion.button>
  )
}

export default LiquidButton
