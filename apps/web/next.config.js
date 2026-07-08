/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API base URL is exposed via NEXT_PUBLIC_API_BASE_URL (see .env.example);
  // never bake secrets (TOMTOM_API_KEY, GEMINI_API_KEY) into the frontend
  // bundle -- all provider calls happen server-side in services/api.
};

module.exports = nextConfig;
