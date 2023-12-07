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
      center: true
    },
    extend: {
      colors: {
        oldschool: "#41FF00"
      },
      spacing: {
        '8xl': '96rem'
      }
    }
  },
  plugins: [],
  safelist: [
    {pattern: /text-orange-./},
    {pattern: /text-red-./},
  ]
}
