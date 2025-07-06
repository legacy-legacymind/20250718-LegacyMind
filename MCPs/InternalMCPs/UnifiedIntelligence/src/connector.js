#!/usr/bin/env node

import net from 'net';
import { createInterface } from 'readline';
import { logger } from './utils/logger.js';

const SOCKET_PATH = '/tmp/unified-intelligence.sock';
const RECONNECT_DELAY = 1000;
const MAX_RECONNECT_ATTEMPTS = 5;

class UnifiedIntelligenceConnector {
  constructor() {
    this.socket = null;
    this.rl = null;
    this.connected = false;
    this.reconnectAttempts = 0;
    this.messageBuffer = [];
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.socket = net.createConnection(SOCKET_PATH, () => {
        this.connected = true;
        this.reconnectAttempts = 0;
        logger.info('Connected to UnifiedIntelligence server');
        
        // Send any buffered messages
        while (this.messageBuffer.length > 0) {
          const message = this.messageBuffer.shift();
          this.socket.write(message);
        }
        
        resolve();
      });

      this.socket.on('data', (data) => {
        // Forward response to stdout
        process.stdout.write(data);
      });

      this.socket.on('error', (err) => {
        if (err.code === 'ENOENT' || err.code === 'ECONNREFUSED') {
          logger.error('UnifiedIntelligence server not running. Please start it with: pm2 start ecosystem.config.js');
        } else {
          logger.error('Socket error:', err);
        }
        this.connected = false;
        reject(err);
      });

      this.socket.on('close', () => {
        this.connected = false;
        logger.info('Disconnected from UnifiedIntelligence server');
        
        // Attempt to reconnect
        if (this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          this.reconnectAttempts++;
          logger.info(`Reconnecting... (attempt ${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
          setTimeout(() => {
            this.connect().catch(() => {
              // Reconnection failed, will be handled by the attempts counter
            });
          }, RECONNECT_DELAY);
        } else {
          logger.error('Max reconnection attempts reached. Exiting.');
          process.exit(1);
        }
      });
    });
  }

  setupStdinReader() {
    this.rl = createInterface({
      input: process.stdin,
      output: null,
      terminal: false
    });

    this.rl.on('line', (line) => {
      const message = line + '\n';
      
      if (this.connected) {
        // Send directly to socket
        this.socket.write(message);
      } else {
        // Buffer the message
        this.messageBuffer.push(message);
        logger.debug('Message buffered, waiting for connection');
      }
    });

    this.rl.on('close', () => {
      logger.info('Stdin closed, shutting down');
      this.shutdown();
    });
  }

  async run() {
    try {
      // Connect to the server
      await this.connect();
      
      // Setup stdin reader
      this.setupStdinReader();
      
      // Handle process signals
      process.on('SIGINT', () => this.shutdown());
      process.on('SIGTERM', () => this.shutdown());
      
    } catch (error) {
      logger.error('Failed to start connector:', error);
      process.exit(1);
    }
  }

  shutdown() {
    logger.info('Shutting down connector');
    
    if (this.rl) {
      this.rl.close();
    }
    
    if (this.socket) {
      this.socket.end();
    }
    
    process.exit(0);
  }
}

// Check if this file is being run directly
if (import.meta.url === `file://${process.argv[1]}`) {
  const connector = new UnifiedIntelligenceConnector();
  connector.run().catch((error) => {
    logger.error('Fatal error:', error);
    process.exit(1);
  });
}

export { UnifiedIntelligenceConnector };