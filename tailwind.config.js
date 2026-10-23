/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'rgb(var(--rgb-ink) / <alpha-value>)',
        paper: 'rgb(var(--rgb-paper) / <alpha-value>)',
        muted: 'rgb(var(--rgb-muted) / <alpha-value>)',
        olive: 'rgb(var(--rgb-olive) / <alpha-value>)',
        cyan: 'rgb(var(--rgb-cyan) / <alpha-value>)',
        alert: 'rgb(var(--rgb-alert) / <alpha-value>)',
      },
      fontFamily: {
        display: ['var(--font-sans)'],
        editorial: ['var(--font-sans)'],
        sans: ['var(--font-sans)'],
      },
      transitionTimingFunction: {
        'out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
}
