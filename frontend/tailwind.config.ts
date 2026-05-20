import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        trovamo: {
          'warm-white':  '#FAF7F2',
          'cream':       '#F0EAE3',
          'stone':       '#E2DDD7',
          'sand':        '#D5CFC8',
          'muted':       '#9B948D',
          'secondary':   '#6B6560',
          'primary':     '#1C1917',
          'accent-50':   '#FAF0EB',
          'accent-100':  '#F5D9CE',
          'accent-200':  '#EAB89F',
          'accent-400':  '#C96956',
          'accent-600':  '#8B6F5E',
          'accent-800':  '#5C3D30',
          'score-high':  '#7B9B7E',
          'score-mid':   '#D4A574',
          'score-low':   '#C96956',
        },
      },
    },
  },
  plugins: [],
}
export default config
