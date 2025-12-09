/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  experimental: {
    outputFileTracingRoot: path.join(__dirname, '../')
  },
  // Add host configuration for Railway
  server: {
    host: '0.0.0.0',
    port: process.env.PORT || 3000
  }
}

module.exports = nextConfig
