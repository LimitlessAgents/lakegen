export default {content: [
  './index.html',
  './src/**/*.{js,ts,jsx,tsx}'
],
  theme: {
    extend: {
      colors: {
        canvas: '#FAF9F8',
        panel: '#FFFFFF',
        line: {
          DEFAULT: '#E6E3E0',
          soft: '#F0EDEA',
          strong: '#D5D0CB',
        },
        ink: {
          DEFAULT: '#1A1918',
          muted: '#6E6963',
          faint: '#9C9691',
        },
        accent: {
          DEFAULT: '#0F6F63',
          hover: '#0C5C52',
          soft: '#EAF2F0',
        },
        ok: '#2F7D5E',
        warn: '#96671A',
        err: '#B0432F',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        '2xs': ['11px', '16px'],
      },
      letterSpacing: {
        wider: '0.06em',
      },
      boxShadow: {
        subtle: '0 1px 2px rgba(26,25,24,0.05)',
        pop: '0 12px 32px -12px rgba(26,25,24,0.22)',
      },
      borderRadius: {
        md: '6px',
        lg: '8px',
        xl: '10px',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 200ms ease-out both',
      },
    },
  },
}
