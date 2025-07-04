FROM node:20-alpine

WORKDIR /app

COPY package*.json ./

RUN npm ci --only=production

COPY src/ ./src/
COPY db-schema.sql ./

CMD ["node", "src/index.js"]
