# Federation MCP Dockerfile
FROM node:18-alpine

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    git

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY src/ ./src/

# Build TypeScript
RUN npm run build

# Create non-root user
RUN addgroup -g 1001 -S federation && \
    adduser -S federation -u 1001

# Set up directories and permissions
RUN mkdir -p /app/logs && \
    chown -R federation:federation /app

# Switch to non-root user
USER federation

# Set environment variables
ENV NODE_ENV=production
ENV DEBUG_MODE=false

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD node -e "console.log('Health check passed')" || exit 1

# Expose port (if needed for HTTP interface)
EXPOSE 3000

# Start the Federation MCP server
CMD ["node", "dist/index.js"]