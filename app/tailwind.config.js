/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Aura color palette
        aura: {
          bg: '#1e1e2e',
          surface: '#282838',
          border: '#3d3d5c',
          text: '#cdd6f4',
          muted: '#6c7086',
          accent: '#89b4fa',
          success: '#a6e3a1',
          warning: '#f9e2af',
          error: '#f38ba8',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
