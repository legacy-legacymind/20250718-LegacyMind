FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install dependencies first (for better caching)
COPY package*.json ./
RUN npm install --omit=dev

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create non-root user
RUN adduser -D -u 1001 mcpuser && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Run the MCP server
CMD ["node", "src/index.js"]