FROM node:20-slim AS base

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# NEXT_PUBLIC_API_BASE_URL is baked in at build time for static optimization,
# but is also safe to override at runtime via docker-compose environment --
# it is a public, non-secret URL. Never bake TOMTOM_API_KEY/GEMINI_API_KEY
# into this image; the frontend never calls those providers directly.
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
