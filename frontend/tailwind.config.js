/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        hitl: {
          base:           'rgb(var(--hitl-base) / <alpha-value>)',
          surface:        'rgb(var(--hitl-surface) / <alpha-value>)',
          'surface-hover':'rgb(var(--hitl-surface-hover) / <alpha-value>)',
          pending:        'rgb(var(--hitl-pending) / <alpha-value>)',
          approved:       'rgb(var(--hitl-approved) / <alpha-value>)',
          rejected:       'rgb(var(--hitl-rejected) / <alpha-value>)',
          escalated:      'rgb(var(--hitl-escalated) / <alpha-value>)',
          active:         'rgb(var(--hitl-active) / <alpha-value>)',
          'klein-blue':   'rgb(var(--hitl-klein-blue) / <alpha-value>)',
          muted:          'rgb(var(--hitl-muted) / <alpha-value>)',
          secondary:      'rgb(var(--hitl-secondary) / <alpha-value>)',
          // Semantic tokens for text / borders (theme-aware)
          'text-primary':   'var(--hitl-text-primary)',
          'text-secondary': 'var(--hitl-text-secondary)',
          border:           'var(--hitl-border)',
          input:            'var(--hitl-input)',
        }
      },
      fontFamily: {
        heading: ['"Cabinet Grotesk"', 'sans-serif'],
        body: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
