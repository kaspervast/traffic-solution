FROM node:20-slim AS base

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# NEXT_PUBLIC_API_BASE_URL is inlined into the client bundle by `next build`
# and CANNOT be changed later via docker-compose `environment:` -- Next.js
# only reads NEXT_PUBLIC_* at build time. Pass it as a build arg instead
# (e.g. `build.args` in docker-compose). Never bake TOMTOM_API_KEY/
# GEMINI_API_KEY into this image; the frontend never calls those providers
# directly.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
