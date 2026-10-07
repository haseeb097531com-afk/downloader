/** @type {import('next').NextConfig} */
import withPWA from '@ducanh2912/next-pwa';

const withPWAConfig = withPWA({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
  runtimeCaching: [
    {
      urlPattern: /^https?:\/\/.*\/_next\/static\//,
      handler: 'CacheFirst',
      options: {
        cacheName: 'next-static',
        expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 30 },
      },
    },
    {
      urlPattern: /^https?:\/\/.*\/(api|search|saved-searches|auth|settings|library|queue|downloads|profiles|plugins|cloud|schedules|moderation|analytics|system|providers|desktop|analysis|bulk|dedup|collections)\/.*$/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'api-routes',
        expiration: { maxEntries: 200, maxAgeSeconds: 60 * 5 },
        networkTimeoutSeconds: 5,
        backgroundSync: { name: 'api-queue', options: { maxRetentionTime: 60 * 60 } },
      },
    },
    {
      urlPattern: /^https?:\/\/.*$/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'shell',
        expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 },
        networkTimeoutSeconds: 5,
        offlineFallback: '/offline',
      },
    },
  ],
});

const nextConfig = {
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'i.ytimg.com' },
      { protocol: 'https', hostname: '*.tiktokcdn.com' },
      { protocol: 'https', hostname: '*.cdninstagram.com' },
      { protocol: 'https', hostname: 'pbs.twimg.com' },
    ],
  },
};

export default withPWAConfig(nextConfig);
