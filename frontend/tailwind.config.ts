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
        // HomeFit Color Palette
        'homefit': {
          // Primary Colors
          'bg-base': '#E8DCC8',        // Warm Khaki
          'bg-secondary': '#F8F6F2',   // Soft Cream
          // Accent Colors
          'accent-primary': '#7B9B7E',   // Sage Green
          'accent-secondary': '#C96956', // Terracotta
          // Text Colors
          'text-primary': '#2D3436',     // Charcoal Gray
          'text-secondary': '#6C7A89',   // Medium Gray
          'text-white': '#FFFFFF',       // White
          // Data Visualization Gradient
          'score-high': '#7B9B7E',       // Sage Green
          'score-mid': '#D4A574',       // Amber Gold
          'score-low': '#C96956',        // Terracotta
          // Utility Colors
          'success': '#7B9B7E',          // Sage Green
          'warning': '#D4A574',         // Amber
          'error': '#C96956',            // Terracotta
          'info': '#8BA5B5',             // Soft Blue-Gray
        },
      },
    },
  },
  plugins: [],
}
export default config
