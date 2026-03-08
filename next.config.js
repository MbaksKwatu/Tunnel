/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // jsPDF's Node.js build tries to require() 'canvas' at module-eval time,
  // which hangs indefinitely when the native module is absent. Marking jspdf
  // and jspdf-autotable as server-external packages prevents Next.js / webpack
  // from ever evaluating them during server-side compilation. They are only
  // loaded by the browser at click time via the dynamic import() in page.tsx.
  experimental: {
    serverExternalPackages: ['jspdf', 'jspdf-autotable'],
  },
};

module.exports = nextConfig;
