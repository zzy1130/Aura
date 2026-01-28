/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // Disable server-side features for Electron
  trailingSlash: true,
  // Use relative paths for Electron file:// loading (production only)
  // In dev mode, use absolute paths so nested routes like /landing work
  assetPrefix: process.env.NODE_ENV === 'production' ? './' : undefined,
  // Fix for react-pdf and pdfjs-dist
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    config.resolve.alias.encoding = false;
    return config;
  },
};

module.exports = nextConfig;
