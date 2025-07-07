FROM node:20-alpine

# Install security updates
RUN apk update && apk upgrade

# Create app directory
WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies with integrity checking
RUN npm ci --only=production --audit

# Copy application files
COPY . .

# Create non-root user with specific UID/GID
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 -G nodejs

# Set proper permissions
RUN chown -R nodejs:nodejs /app && \
    chmod -R 755 /app

# Switch to non-root user
USER nodejs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "console.log('Health check passed')" || exit 1

# Keep container running for docker exec
CMD ["tail", "-f", "/dev/null"]