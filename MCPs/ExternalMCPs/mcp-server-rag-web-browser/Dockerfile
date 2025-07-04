FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy built distribution and source
COPY dist/ ./dist/
COPY src/ ./src/
COPY LICENSE ./

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Change ownership and switch user
RUN chown -R nodejs:nodejs /app
USER nodejs

# Expose stdio for MCP communication
EXPOSE 3000

# Start the MCP server
CMD ["node", "dist/index.js"]