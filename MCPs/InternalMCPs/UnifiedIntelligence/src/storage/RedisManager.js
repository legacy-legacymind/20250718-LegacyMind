import { createClient } from 'redis';

let instance = null;

export class RedisManager {
  constructor() {
    if (instance) {
      return instance;
    }
    this.client = null;
    this.pubClient = null;
    this.subClient = null;
    this.modules = {};
    instance = this;
  }

  async connect() {
    if (this.client) {
      return this.client;
    }

    // Build Redis URL from environment variables
    const redisHost = process.env.REDIS_HOST || 'localhost';
    const redisPort = process.env.REDIS_PORT || '6379';
    const redisPassword = process.env.REDIS_PASSWORD;
    
    const redisUrl = redisPassword 
      ? `redis://:${redisPassword}@${redisHost}:${redisPort}`
      : `redis://${redisHost}:${redisPort}`;

    // Create main client with all modules
    this.client = createClient({
      url: redisUrl,
      socket: {
        reconnectStrategy: (retries) => Math.min(retries * 50, 500)
      }
    });

    // Create pub/sub clients
    this.pubClient = this.client.duplicate();
    this.subClient = this.client.duplicate();

    this.client.on('error', (err) => console.error('Redis Client Error', err));
    this.pubClient.on('error', (err) => console.error('Redis Pub Client Error', err));
    this.subClient.on('error', (err) => console.error('Redis Sub Client Error', err));

    await this.client.connect();
    await this.pubClient.connect();
    await this.subClient.connect();

    // Verify Redis 8.0 modules
    await this.verifyModules();
    
    // Initialize search indexes
    await this.initializeIndexes();

    return this.client;
  }

  async verifyModules() {
    try {
      const modules = await this.client.sendCommand(['MODULE', 'LIST']);
      const requiredModules = ['ReJSON', 'search', 'timeseries', 'bf'];
      
      for (const required of requiredModules) {
        const found = modules.some(mod => 
          mod[1].toLowerCase().includes(required.toLowerCase())
        );
        this.modules[required] = found;
        if (!found) {
          console.warn(`Redis module ${required} not found. Some features will be limited.`);
        } else {
          console.log(`Redis module ${required} is available`);
        }
      }
    } catch (err) {
      console.error('Could not verify Redis modules:', err);
    }
  }

  async initializeIndexes() {
    // Create search index for thoughts
    try {
      await this.client.ft.create('idx:thoughts', {
        '$.content': { type: 'TEXT', AS: 'content' },
        '$.tags[*]': { type: 'TAG', AS: 'tags' },
        '$.mode': { type: 'TAG', AS: 'mode' },
        '$.framework': { type: 'TAG', AS: 'framework' },
        '$.significance': { type: 'NUMERIC', AS: 'significance' },
        '$.confidence': { type: 'NUMERIC', AS: 'confidence' }
      }, {
        ON: 'JSON',
        PREFIX: ['thought:']
      });
      console.log('Thoughts search index created');
    } catch (err) {
      if (!err.message.includes('Index already exists')) {
        console.error('Error creating thoughts index:', err);
      }
    }

    // Create search index for contexts
    try {
      await this.client.ft.create('idx:contexts', {
        '$.data': { type: 'TEXT', AS: 'data' },
        '$.type': { type: 'TAG', AS: 'type' }
      }, {
        ON: 'JSON',
        PREFIX: ['context:']
      });
      console.log('Contexts search index created');
    } catch (err) {
      if (!err.message.includes('Index already exists')) {
        console.error('Error creating contexts index:', err);
      }
    }
  }

  async disconnect() {
    if (this.client) {
      await this.client.quit();
      await this.pubClient.quit();
      await this.subClient.quit();
      this.client = null;
      this.pubClient = null;
      this.subClient = null;
    }
  }

  getClient() {
    if (!this.client) {
      throw new Error('Redis client not connected. Call connect() first.');
    }
    return this.client;
  }

  getPubClient() {
    if (!this.pubClient) {
      throw new Error('Redis pub client not connected. Call connect() first.');
    }
    return this.pubClient;
  }

  getSubClient() {
    if (!this.subClient) {
      throw new Error('Redis sub client not connected. Call connect() first.');
    }
    return this.subClient;
  }
}