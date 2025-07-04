# Use an official Node.js runtime as a parent image
FROM node:20-alpine

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install production dependencies
RUN npm ci --only=production

# Copy the rest of the application's source code
COPY src/ ./src/

# Set environment variables for Redis connection and instance detection
ENV REDIS_HOST=legacymind_redis
ENV REDIS_PORT=6379
ENV INSTANCE_ID=unified_intelligence
ENV CLAUDE_INSTANCE=""
ENV CONTAINER_NAME="unified_intelligence"

# Create a non-root user to run the application
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Change ownership of the app directory
RUN chown -R nodejs:nodejs /app

# Switch to the non-root user
USER nodejs

# Command to run the application
CMD ["node", "src/index.js"]

