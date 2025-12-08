import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        base: {
          900: '#0f172a', // Dark Slate
          950: '#020617', // Deep Midnight
        },
        accent: {
          cyan: '#22d3ee', // Cyber Cyan
          indigo: '#818cf8', // Cosmic Indigo
        },
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        dark: {
          bg: '#0D0F12',
          card: '#1B1E23',
          cardHover: '#23272E',
        },
      },
      boxShadow: {
        'inner-dark': 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.6)',
        'glow-indigo': '0 0 20px rgba(129, 140, 248, 0.5)',
        'glow-cyan': '0 0 20px rgba(34, 211, 238, 0.5)',
      },
      backgroundImage: {
        'gradient-cyan-green': 'linear-gradient(to right, #22d3ee, #4ade80)',
      },
    },
  },
  plugins: [],
};
export default config;


