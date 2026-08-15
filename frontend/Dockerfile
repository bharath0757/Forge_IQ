FROM node:20-alpine AS builder

WORKDIR /app

# Install build dependencies
COPY package*.json ./
RUN npm ci

# Copy application source
COPY . .

# Build Next.js application
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# Production runtime image
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

COPY package*.json ./
RUN npm ci --only=production

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.* ./

EXPOSE 3000

CMD ["npm", "start"]
