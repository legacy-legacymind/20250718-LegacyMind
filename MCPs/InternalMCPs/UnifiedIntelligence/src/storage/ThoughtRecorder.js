export class ThoughtRecorder {
  constructor(redisClient) {
    this.redis = redisClient;
    this.bloomFilter = 'thoughts:bloom';
  }

  async recordThought(sessionId, thoughtData) {
    const streamKey = `thoughts:session:${sessionId}`;
    const thoughtId = thoughtData.thoughtId;
    const thoughtKey = `thought:${thoughtId}`;
    
    // Check bloom filter for duplicate
    const isDuplicate = await this.redis.bf.exists(this.bloomFilter, thoughtData.content);
    if (isDuplicate) {
      console.log(`[BLOOM] Potential duplicate thought detected: ${thoughtId}`);
      // Still process but flag as potential duplicate
      thoughtData.potentialDuplicate = true;
    }
    
    // Add to bloom filter
    await this.redis.bf.add(this.bloomFilter, thoughtData.content);
    
    // Store thought with RedisJSON
    const thoughtDoc = {
      ...thoughtData,
      sessionId,
      recordedAt: Date.now()
    };
    
    await this.redis.sendCommand([
      'JSON.SET', 
      thoughtKey, 
      '$', 
      JSON.stringify(thoughtDoc)
    ]);
    
    // Add to stream with MAXLEN
    await this.redis.xAdd(
      streamKey, 
      '*',
      {
        thoughtId,
        content: thoughtData.content,
        significance: thoughtData.significance.toString(),
        confidence: thoughtData.confidence?.toString() || '1.0',
        mode: thoughtData.mode,
        tags: JSON.stringify(thoughtData.tags || [])
      },
      { MAXLEN: { strategy: 'APPROX', threshold: 10000 } }
    );
    
    // Record metrics in time series
    await this.recordMetrics(sessionId, thoughtData);
    
    return thoughtId;
  }

  async recordMetrics(sessionId, thoughtData) {
    const now = Date.now();
    
    // Record significance time series
    try {
      await this.redis.ts.add(
        `metrics:significance:${sessionId}`,
        now,
        thoughtData.significance,
        {}
      );
    } catch (err) {
      if (!err.message.includes('key does not exist')) throw err;
      // Create time series if it doesn't exist
      await this.redis.ts.create(`metrics:significance:${sessionId}`, {
        LABELS: { session: sessionId, metric: 'significance' }
      });
      await this.redis.ts.add(
        `metrics:significance:${sessionId}`,
        now,
        thoughtData.significance
      );
    }
    
    // Record confidence time series
    try {
      await this.redis.ts.add(
        `metrics:confidence:${sessionId}`,
        now,
        thoughtData.confidence || 1.0,
        {}
      );
    } catch (err) {
      if (!err.message.includes('key does not exist')) throw err;
      await this.redis.ts.create(`metrics:confidence:${sessionId}`, {
        LABELS: { session: sessionId, metric: 'confidence' }
      });
      await this.redis.ts.add(
        `metrics:confidence:${sessionId}`,
        now,
        thoughtData.confidence || 1.0
      );
    }
  }

  async getThought(thoughtId) {
    const thoughtKey = `thought:${thoughtId}`;
    const result = await this.redis.sendCommand(['JSON.GET', thoughtKey, '$']);
    if (!result) return null;
    return JSON.parse(result)[0];
  }

  async searchThoughts(query, options = {}) {
    const {
      mode,
      minSignificance,
      tags,
      limit = 20,
      offset = 0
    } = options;
    
    // Build search query
    let searchQuery = [];
    
    // Text search
    if (query) {
      searchQuery.push(query);
    }
    
    // Filters
    if (mode) {
      searchQuery.push(`@mode:{${mode}}`);
    }
    
    if (minSignificance) {
      searchQuery.push(`@significance:[${minSignificance} +inf]`);
    }
    
    if (tags && tags.length > 0) {
      searchQuery.push(tags.map(t => `@tags:{${t}}`).join(' '));
    }
    
    const finalQuery = searchQuery.length > 0 ? searchQuery.join(' ') : '*';
    
    const results = await this.redis.ft.search('idx:thoughts', finalQuery, {
      RETURN: ['content', 'significance', 'confidence', 'mode', 'tags', 'sessionId'],
      SORTBY: 'significance',
      DIRECTION: 'DESC',
      LIMIT: { from: offset, size: limit }
    });
    
    return {
      total: results.total,
      thoughts: results.documents.map(doc => ({
        id: doc.id,
        ...doc.value
      }))
    };
  }

  async getSessionMetrics(sessionId, timeRange = '1h') {
    const now = Date.now();
    const ranges = {
      '1h': now - 3600000,
      '6h': now - 21600000,
      '24h': now - (24 * 60 * 60 * 1000)
    };
    const fromTime = ranges[timeRange] || ranges['1h'];
    
    // Get aggregated metrics
    const [significance, confidence] = await Promise.all([
      this.redis.ts.range(
        `metrics:significance:${sessionId}`,
        fromTime,
        now,
        { AGGREGATION: { type: 'AVG', timeBucket: 60000 } } // 1 minute buckets
      ),
      this.redis.ts.range(
        `metrics:confidence:${sessionId}`,
        fromTime,
        now,
        { AGGREGATION: { type: 'AVG', timeBucket: 60000 } }
      )
    ]);
    
    return {
      significance: significance.map(s => ({ time: s.timestamp, value: s.value })),
      confidence: confidence.map(c => ({ time: c.timestamp, value: c.value }))
    };
  }
}