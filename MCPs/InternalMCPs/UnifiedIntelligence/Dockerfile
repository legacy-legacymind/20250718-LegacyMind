FROM node:20-alpine

# Install security updates
RUN apk update && apk upgrade

# Create app directory
WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies with integrity checking and PM2 globally
RUN npm ci --only=production --audit && \
    npm install -g pm2

# Copy application files
COPY . .

# Create non-root user with specific UID/GID
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 -G nodejs

# Create logs directory for PM2
RUN mkdir -p /app/logs && \
    chown -R nodejs:nodejs /app && \
    chmod -R 755 /app

# Switch to non-root user
USER nodejs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD pm2 ping || exit 1

# Start with PM2
CMD ["npm", "run", "start:pm2"]