/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.{html,js}',
  ],
  theme: {
    fontSize: {
      xs: ['10px', '16px'],
      sm: ['14px', '20px'],
      base: ['16px', '24px'],
      lg: ['20px', '28px'],
      xl: ['24px', '32px'],
    },
    container: {
      center: true,
      padding: '1rem',
    },
    extend: {
      colors: {
        oldschool: "#41FF00",
      },
      spacing: {
        '8xl': '96rem',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeOut: {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
        zoomIn: {
          '0%': { transform: 'scale(0.9)' },
          '100%': { transform: 'scale(1)' },
        },
        zoomOut: {
          '0%': { transform: 'scale(1)' },
          '100%': { transform: 'scale(0.9)' },
        },
      },
      animation: {
        fadeIn: 'fadeIn 150ms ease forwards',
        fadeOut: 'fadeOut 150ms ease forwards',
        zoomIn: 'zoomIn 150ms ease forwards',
        zoomOut: 'zoomOut 150ms ease forwards',
      },
    },
  },
  plugins: [],
  safelist: [
    { pattern: /text-orange-[0-9]{3}/ },
    { pattern: /text-red-[0-9]{3}/ },
  ],
}
