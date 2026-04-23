import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        sand: {
          50: '#fcf7ef',
          100: '#f8ecd8',
          200: '#f0d9b0',
          300: '#e7c07f',
          400: '#d59f44',
          500: '#bc8422',
          600: '#98661a',
          700: '#785019',
          800: '#573b17',
          900: '#3d2912',
        },
        ink: '#101828',
        slate: '#344054',
        coral: '#f04438',
        teal: '#0f766e',
      },
      boxShadow: {
        panel: '0 20px 60px rgba(16, 24, 40, 0.12)',
      },
      backgroundImage: {
        'dashboard-glow': 'radial-gradient(circle at top left, rgba(188, 132, 34, 0.18), transparent 34%), radial-gradient(circle at top right, rgba(15, 118, 110, 0.14), transparent 30%), linear-gradient(180deg, #fdfaf5 0%, #fff8ee 100%)',
      },
    },
  },
  plugins: [],
} satisfies Config;
