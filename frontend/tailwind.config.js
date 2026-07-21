/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        industrial: {
          50:  '#f0f4ff',
          100: '#dce6fd',
          500: '#3b6fd4',
          700: '#1e3fa8',
          900: '#0f1f5c',
        },
        hazard: {
          yellow: '#fbbf24',
          orange: '#f97316',
          red:    '#ef4444',
        }
      }
    },
  },
  plugins: [],
}
