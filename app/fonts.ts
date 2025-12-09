import localFont from 'next/font/local';
import { Inter } from 'next/font/google';

// Inter font for body text
export const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

// Agrandir Narrow for display/headings
// Place Agrandir-Narrow.otf in /public/fonts/agrandir/
export const agrandirNarrow = localFont({
  src: '../public/fonts/agrandir/Agrandir-Narrow.otf',
  variable: '--font-agrandir-narrow',
  display: 'swap',
  fallback: ['Inter', 'system-ui', 'sans-serif'],
});
