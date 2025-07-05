const { createClient } = require('redis');
const EventEmitter = require('events');

class RedisManager extends EventEmitter {
  constructor(config = {}) {
    super();
    this.config = {
      host: config.host || 'localhost',
      port: config.port || 6379,
      maxRetries: config.maxRetries || 3,
      retryDelay: config.retryDelay || 1000,
      circuitBreakerThreshold: config.circuitBreakerThreshold || 5,
      circuitBreakerResetTime: config.circuitBreakerResetTime || 60000,
      poolSize: config.poolSize || 5,
      enableReadReplicas: config.enableReadReplicas || false,
      readReplicaHosts: config.readReplicaHosts || [],
      ...config
    };
    
    this.connectionPool = new Map();
    this.pubsubClients = new Map();
    this.subscriptions = new Map();
    this.circuitBreaker = {
      failures: 0,
      isOpen: false,
      lastFailTime: null
    };
    this.metrics = {
      totalConnections: 0,
      activeConnections: 0,
      failedConnections: 0,
      totalRequests: 0,
      failedRequests: 0
    };
  }

  async getConnection(purpose = 'default') {
    if (this.circuitBreaker.isOpen) {
      if (Date.now() - this.circuitBreaker.lastFailTime < this.config.circuitBreakerResetTime) {
        throw new Error('Circuit breaker is open');
      }
      this.circuitBreaker.isOpen = false;
      this.circuitBreaker.failures = 0;
    }

    if (this.connectionPool.has(purpose)) {
      const connection = this.connectionPool.get(purpose);
      if (connection.isOpen) {
        return connection;
      }
    }

    try {
      const client = await this.createClient();
      this.connectionPool.set(purpose, client);
      this.metrics.totalConnections++;
      this.metrics.activeConnections++;
      return client;
    } catch (error) {
      this.handleConnectionFailure(error);
      throw error;
    }
  }

  async createClient() {
    const client = createClient({
      socket: {
        host: this.config.host,
        port: this.config.port,
        reconnectStrategy: (retries) => {
          if (retries > this.config.maxRetries) {
            return new Error('Max retries exceeded');
          }
          return this.config.retryDelay * Math.pow(2, retries);
        }
      }
    });

    client.on('error', (err) => {
      console.error('Redis Client Error:', err);
      this.emit('error', err);
    });

    client.on('connect', () => {
      console.log('Redis Client Connected');
      this.emit('connect');
    });

    client.on('ready', () => {
      console.log('Redis Client Ready');
      this.emit('ready');
    });

    client.on('end', () => {
      this.metrics.activeConnections--;
      this.emit('disconnect');
    });

    await client.connect();
    return client;
  }

  handleConnectionFailure(error) {
    this.metrics.failedConnections++;
    this.circuitBreaker.failures++;
    this.circuitBreaker.lastFailTime = Date.now();

    if (this.circuitBreaker.failures >= this.config.circuitBreakerThreshold) {
      this.circuitBreaker.isOpen = true;
      console.error('Circuit breaker opened due to repeated failures');
      this.emit('circuitBreakerOpen');
    }
  }

  async executeCommand(command, args = [], options = {}) {
    const startTime = Date.now();
    this.metrics.totalRequests++;

    try {
      const client = await this.getConnection(options.purpose || 'default');
      const result = await client[command](...args);
      
      this.emit('commandExecuted', {
        command,
        args,
        duration: Date.now() - startTime,
        success: true
      });

      return result;
    } catch (error) {
      this.metrics.failedRequests++;
      this.emit('commandExecuted', {
        command,
        args,
        duration: Date.now() - startTime,
        success: false,
        error
      });
      throw error;
    }
  }

  // Key-Value Operations
  async get(key) {
    return this.executeCommand('get', [key]);
  }

  async set(key, value, options = {}) {
    const args = [key, value];
    if (options.EX) args.push('EX', options.EX);
    if (options.PX) args.push('PX', options.PX);
    if (options.NX) args.push('NX');
    if (options.XX) args.push('XX');
    return this.executeCommand('set', args);
  }

  async del(key) {
    return this.executeCommand('del', [key]);
  }

  async exists(key) {
    return this.executeCommand('exists', [key]);
  }

  async expire(key, seconds) {
    return this.executeCommand('expire', [key, seconds]);
  }

  async ttl(key) {
    return this.executeCommand('ttl', [key]);
  }

  // Hash Operations
  async hSet(key, field, value) {
    return this.executeCommand('hSet', [key, field, value]);
  }

  async hGet(key, field) {
    return this.executeCommand('hGet', [key, field]);
  }

  async hGetAll(key) {
    return this.executeCommand('hGetAll', [key]);
  }

  async hDel(key, field) {
    return this.executeCommand('hDel', [key, field]);
  }

  async hExists(key, field) {
    return this.executeCommand('hExists', [key, field]);
  }

  // List Operations
  async lPush(key, ...values) {
    return this.executeCommand('lPush', [key, ...values]);
  }

  async rPush(key, ...values) {
    return this.executeCommand('rPush', [key, ...values]);
  }

  async lPop(key) {
    return this.executeCommand('lPop', [key]);
  }

  async rPop(key) {
    return this.executeCommand('rPop', [key]);
  }

  async lRange(key, start, stop) {
    return this.executeCommand('lRange', [key, start, stop]);
  }

  async lLen(key) {
    return this.executeCommand('lLen', [key]);
  }

  // Set Operations
  async sAdd(key, ...members) {
    return this.executeCommand('sAdd', [key, ...members]);
  }

  async sRem(key, ...members) {
    return this.executeCommand('sRem', [key, ...members]);
  }

  async sMembers(key) {
    return this.executeCommand('sMembers', [key]);
  }

  async sIsMember(key, member) {
    return this.executeCommand('sIsMember', [key, member]);
  }

  async sCard(key) {
    return this.executeCommand('sCard', [key]);
  }

  // Sorted Set Operations
  async zAdd(key, ...members) {
    return this.executeCommand('zAdd', [key, ...members]);
  }

  async zRem(key, ...members) {
    return this.executeCommand('zRem', [key, ...members]);
  }

  async zRange(key, start, stop, options = {}) {
    const args = [key, start, stop];
    if (options.withScores) args.push('WITHSCORES');
    return this.executeCommand('zRange', args);
  }

  async zScore(key, member) {
    return this.executeCommand('zScore', [key, member]);
  }

  async zRank(key, member) {
    return this.executeCommand('zRank', [key, member]);
  }

  // Pub/Sub Operations
  async publish(channel, message) {
    return this.executeCommand('publish', [channel, message]);
  }

  async subscribe(channel, callback) {
    if (!this.pubsubClients.has(channel)) {
      const client = await this.createClient();
      this.pubsubClients.set(channel, client);
      
      await client.subscribe(channel, (message) => {
        const callbacks = this.subscriptions.get(channel) || [];
        callbacks.forEach(cb => {
          try {
            cb(message, channel);
          } catch (error) {
            console.error(`Error in subscription callback for channel ${channel}:`, error);
          }
        });
      });
    }

    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, []);
    }
    this.subscriptions.get(channel).push(callback);

    return () => this.unsubscribe(channel, callback);
  }

  async unsubscribe(channel, callback) {
    if (!this.subscriptions.has(channel)) return;

    const callbacks = this.subscriptions.get(channel);
    const index = callbacks.indexOf(callback);
    if (index > -1) {
      callbacks.splice(index, 1);
    }

    if (callbacks.length === 0) {
      this.subscriptions.delete(channel);
      const client = this.pubsubClients.get(channel);
      if (client) {
        await client.unsubscribe(channel);
        await client.quit();
        this.pubsubClients.delete(channel);
      }
    }
  }

  // Transaction Operations
  async multi() {
    const client = await this.getConnection('transaction');
    return client.multi();
  }

  // Pipeline Operations
  async pipeline() {
    const client = await this.getConnection('pipeline');
    return client.pipeline();
  }

  // Utility Methods
  async ping() {
    return this.executeCommand('ping');
  }

  async flushDb() {
    return this.executeCommand('flushDb');
  }

  async flushAll() {
    return this.executeCommand('flushAll');
  }

  async keys(pattern) {
    return this.executeCommand('keys', [pattern]);
  }

  async scan(cursor, options = {}) {
    const args = [cursor];
    if (options.match) args.push('MATCH', options.match);
    if (options.count) args.push('COUNT', options.count);
    return this.executeCommand('scan', args);
  }

  // Connection Management
  async disconnect() {
    const disconnectPromises = [];

    // Disconnect all connection pool clients
    for (const [purpose, client] of this.connectionPool) {
      if (client.isOpen) {
        disconnectPromises.push(client.quit());
      }
    }

    // Disconnect all pubsub clients
    for (const [channel, client] of this.pubsubClients) {
      if (client.isOpen) {
        disconnectPromises.push(client.quit());
      }
    }

    await Promise.all(disconnectPromises);
    
    this.connectionPool.clear();
    this.pubsubClients.clear();
    this.subscriptions.clear();
    this.metrics.activeConnections = 0;
    
    this.emit('disconnected');
  }

  // Health Check
  async healthCheck() {
    try {
      const pong = await this.ping();
      return {
        status: 'healthy',
        ping: pong,
        metrics: this.metrics,
        circuitBreaker: {
          isOpen: this.circuitBreaker.isOpen,
          failures: this.circuitBreaker.failures
        }
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        error: error.message,
        metrics: this.metrics,
        circuitBreaker: {
          isOpen: this.circuitBreaker.isOpen,
          failures: this.circuitBreaker.failures
        }
      };
    }
  }

  // Get metrics
  getMetrics() {
    return {
      ...this.metrics,
      connectionPoolSize: this.connectionPool.size,
      pubsubChannels: this.pubsubClients.size,
      circuitBreakerStatus: this.circuitBreaker.isOpen ? 'open' : 'closed'
    };
  }
}

module.exports = RedisManager;