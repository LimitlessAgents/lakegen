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
        ok: {
          DEFAULT: '#2F7D5E',
          soft: '#EAF4EF',
        },
        warn: '#96671A',
        err: {
          DEFAULT: '#B0432F',
          soft: '#FCF6F5',
          border: '#EBD5D0',
          strong: '#7C3323',
        },
        badge: {
          glue: '#7A5B12',
          'glue-soft': '#FBF5E7',
          'glue-border': '#EEE3C9',
          sql: '#3F5C86',
          'sql-soft': '#EEF2F8',
          'sql-border': '#D9E2EF',
          'rest-border': '#D6E5E1',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        '2xs': ['11px', '16px'],
        xs: ['12px', '16px'],
        sm: ['13px', '20px'],
        base: ['14px', '22px'],
        lg: ['15px', '24px'],
        xl: ['19px', '28px'],
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
      spacing: {
        header: '52px',
      },
      zIndex: {
        dropdown: '20',
        overlay: '30',
        panel: '40',
        popover: '50',
        toast: '60',
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
