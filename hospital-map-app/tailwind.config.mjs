/** @type {import('tailwindcss').Config} */
const config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        blue: {
          800: '#1e40af',
          900: '#1e3a8a',
        },
        gray: {
          700: '#374151',
          800: '#1f2937',
          900: '#111827',
        },
        green: {
          300: '#86efac',
          900: '#14532d',
        },
        red: {
          300: '#fca5a5',
          900: '#7f1d1d',
        },
        cyber: {
          'neon-green': '#00FFA0',
          'neon-blue': '#00AFFF',
          'neon-purple': '#B400FF',
          'dark-1': '#020510',
          'dark-2': '#050A19',
        }
      },
      animation: {
        'tron-scan': 'tron-scan 3s infinite linear',
        'float': 'float 3s ease-in-out infinite',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'cyber-glitch': 'cyber-glitch 500ms infinite linear alternate-reverse',
        'scan': 'scan 3s linear infinite',
      },
      keyframes: {
        'tron-scan': {
          '0%': { left: '-100%' },
          '100%': { left: '200%' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '0.5' },
          '50%': { opacity: '1' },
        },
        'cyber-glitch': {
          '0%': {
            clipPath: 'inset(50% 0 30% 0)',
            transform: 'skew(0.15turn, 2deg)',
          },
          '20%': {
            clipPath: 'inset(10% 0 60% 0)',
            transform: 'skew(-0.15turn, -2deg)',
          },
          '40%': {
            clipPath: 'inset(40% 0 40% 0)',
            transform: 'skew(0.15turn, 2deg)',
          },
          '60%': {
            clipPath: 'inset(20% 0 50% 0)',
            transform: 'skew(-0.15turn, -2deg)',
          },
          '80%': {
            clipPath: 'inset(30% 0 30% 0)',
            transform: 'skew(0.15turn, 2deg)',
          },
          '100%': {
            clipPath: 'inset(50% 0 30% 0)',
            transform: 'skew(-0.15turn, -2deg)',
          },
        },
        'scan': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
};

export default config; 