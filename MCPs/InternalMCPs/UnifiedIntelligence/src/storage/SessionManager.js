import { v4 as uuidv4 } from 'uuid';

export class SessionManager {
  constructor(redisClient) {
    this.redis = redisClient;
  }

  async createSession(instanceId, metadata = {}) {
    const sessionId = uuidv4();
    const sessionKey = `session:${sessionId}`;
    const now = Date.now();
    
    const sessionData = {
      sessionId,
      instanceId,
      task: metadata.task || 'general',
      goals: metadata.goals || [],
      title: metadata.title || `Session ${new Date().toISOString()}`,
      description: metadata.description || '',
      createdAt: now,
      lastActivity: now,
      active: true
    };
    
    // Store session with RedisJSON
    await this.redis.sendCommand([
      'JSON.SET',
      sessionKey,
      '$',
      JSON.stringify(sessionData)
    ]);
    
    // Initialize time series for session metrics
    await this.initializeMetrics(sessionId);
    
    // Track active session
    await this.redis.set(`active_session:${instanceId}`, sessionId);
    await this.redis.set('ui:last_instance', instanceId);
    
    // Initialize bloom filter for this session
    await this.redis.bf.reserve(`session:bloom:${sessionId}`, 0.01, 10000);
    
    return sessionData;
  }

  async initializeMetrics(sessionId) {
    const metrics = [
      { key: `metrics:thoughts:${sessionId}`, label: 'thoughts_count' },
      { key: `metrics:significance:${sessionId}`, label: 'avg_significance' },
      { key: `metrics:confidence:${sessionId}`, label: 'avg_confidence' },
      { key: `metrics:processing:${sessionId}`, label: 'processing_time_ms' }
    ];
    
    for (const metric of metrics) {
      try {
        await this.redis.ts.create(metric.key, {
          DUPLICATE_POLICY: 'LAST',
          LABELS: { 
            session: sessionId, 
            metric: metric.label 
          }
        });
      } catch (err) {
        if (!err.message.includes('key already exists')) {
          console.error(`Error creating metric ${metric.key}:`, err);
        }
      }
    }
  }

  async recordMetric(sessionId, metricType, value) {
    const metricKey = `metrics:${metricType}:${sessionId}`;
    try {
      await this.redis.ts.add(metricKey, Date.now(), value);
    } catch (err) {
      console.error(`Error recording metric ${metricType}:`, err);
    }
  }

  async getSessionMetrics(sessionId) {
    const now = Date.now();
    const hourAgo = now - 3600000;
    
    const metricTypes = ['thoughts', 'significance', 'confidence', 'processing'];
    const metrics = {};
    
    for (const type of metricTypes) {
      try {
        const data = await this.redis.ts.range(
          `metrics:${type}:${sessionId}`,
          hourAgo,
          now,
          { AGGREGATION: { type: 'AVG', timeBucket: 300000 } } // 5 minute buckets
        );
        metrics[type] = data;
      } catch (err) {
        metrics[type] = [];
      }
    }
    
    // Get summary stats
    const summary = {};
    for (const type of metricTypes) {
      try {
        const info = await this.redis.ts.info(`metrics:${type}:${sessionId}`);
        summary[type] = {
          total: info.totalSamples,
          lastValue: info.lastValue,
          firstTimestamp: info.firstTimestamp,
          lastTimestamp: info.lastTimestamp
        };
      } catch (err) {
        summary[type] = null;
      }
    }
    
    return { timeSeries: metrics, summary };
  }

  async getCurrentSession(instanceId) {
    const sessionId = await this.redis.get(`active_session:${instanceId}`);
    if (!sessionId) return null;
    
    const sessionKey = `session:${sessionId}`;
    const result = await this.redis.sendCommand(['JSON.GET', sessionKey, '$']);
    
    if (!result) return null;
    const session = JSON.parse(result)[0];
    
    // Add current metrics to session
    const metrics = await this.getSessionMetrics(sessionId);
    session.metrics = metrics.summary;
    
    return session;
  }

  async endSession(instanceId) {
    const session = await this.getCurrentSession(instanceId);
    if (!session) return { success: false, message: 'No active session' };
    
    const sessionKey = `session:${session.sessionId}`;
    
    // Atomic update to mark session as inactive
    const endSessionScript = `
      local key = KEYS[1]
      local now = ARGV[1]
      redis.call('JSON.SET', key, '$.active', 'false')
      redis.call('JSON.SET', key, '$.endedAt', now)
      return redis.call('JSON.GET', key, '$')
    `;
    
    const result = await this.redis.eval(endSessionScript, {
      keys: [sessionKey],
      arguments: [Date.now().toString()]
    });
    
    await this.redis.del(`active_session:${instanceId}`);
    
    // Get final metrics
    const finalMetrics = await this.getSessionMetrics(session.sessionId);
    
    return { 
      success: true, 
      session: JSON.parse(result)[0],
      finalMetrics 
    };
  }
}