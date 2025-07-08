/**
 * Memory Formation Pipeline - The heart of UnifiedIntelligence
 * 
 * Processes thoughts through analysis, storage, and pattern detection
 */
import { v4 as uuidv4 } from 'uuid';
import { AnalyzerOrchestrator } from '../analyzers/index.js';
import { FrameworkEngine } from '../frameworks/index.js';

export class MemoryFormationPipeline {
  constructor(redisManager, sessionManager, thoughtRecorder, instanceId) {
    this.redis = redisManager.getClient();
    this.pubClient = redisManager.getPubClient();
    this.sessionManager = sessionManager;
    this.thoughtRecorder = thoughtRecorder;
    this.instanceId = instanceId;
    
    this.analyzerOrchestrator = new AnalyzerOrchestrator();
    this.frameworkEngine = new FrameworkEngine();
    
    // Metrics tracking
    this.metrics = {
      thoughtsProcessed: 0,
      totalProcessingTime: 0,
      errors: 0
    };
  }

  async analyzeOnly(content, options = {}) {
    // Analyze without storing - for ui_think tool
    const analysis = await this.analyzerOrchestrator.analyzeThought(content);
    
    // Get framework suggestions
    const frameworkSuggestions = this.frameworkEngine.suggestFrameworks(
      analysis.mode,
      analysis.significance,
      content
    );
    
    return {
      ...analysis,
      frameworks: frameworkSuggestions,
      stored: false
    };
  }

  async processThought(instanceId, content, options = {}) {
    const startTime = Date.now();
    const thoughtId = uuidv4();
    
    try {
      // Get or create session
      let session = await this.sessionManager.getCurrentSession(instanceId);
      if (!session) {
        session = await this.sessionManager.createSession(instanceId, {
          task: options.task || 'general',
          goals: options.goals || []
        });
      }
      
      const sessionId = session.sessionId;
      
      // Analyze the thought
      const analysis = await this.analyzerOrchestrator.analyzeThought(content, {
        sessionId,
        thoughtId,
        instanceId
      });
      
      // Prepare thought data
      const thoughtData = {
        thoughtId,
        content,
        mode: analysis.mode,
        significance: analysis.significance,
        tags: analysis.tags,
        frameworks: analysis.frameworks.map(f => f.framework),
        confidence: analysis.metrics.overallConfidence,
        analysis: analysis.analysis,
        metadata: {
          instanceId,
          sessionId,
          timestamp: Date.now(),
          processingTimeMs: Date.now() - startTime,
          ...options.metadata
        }
      };
      
      // Record the thought
      await this.thoughtRecorder.recordThought(sessionId, thoughtData, instanceId);
      
      // Update session activity
      await this.updateSessionActivity(sessionId);
      
      // Record processing metrics
      const processingTime = Date.now() - startTime;
      await this.sessionManager.recordMetric(sessionId, 'processing', processingTime);
      await this.sessionManager.recordMetric(sessionId, 'thoughts', 1);
      
      // Publish thought processed event
      await this.publishThoughtEvent(thoughtData);
      
      // Check for patterns and triggers
      const patterns = await this.detectPatterns(sessionId, thoughtData);
      
      // Apply auto-frameworks if enabled
      let frameworkResults = null;
      if (options.autoFramework && analysis.frameworks.length > 0) {
        const topFramework = analysis.frameworks[0];
        if (topFramework.confidence > 0.7) {
          frameworkResults = await this.applyFramework(
            sessionId,
            topFramework.framework,
            thoughtId
          );
        }
      }
      
      // Update metrics
      this.metrics.thoughtsProcessed++;
      this.metrics.totalProcessingTime += processingTime;
      
      // Prepare result
      const result = {
        success: true,
        thoughtId,
        sessionId,
        mode: analysis.mode,
        significance: analysis.significance,
        tags: analysis.tags,
        frameworks: analysis.frameworks,
        patterns,
        frameworkResults,
        metrics: {
          processingTimeMs: processingTime,
          overallConfidence: analysis.metrics.overallConfidence
        },
        metadata: thoughtData.metadata
      };
      
      // Store result in short-term cache
      await this.cacheResult(thoughtId, result);
      
      return result;
      
    } catch (error) {
      console.error('Error in memory formation pipeline:', error);
      this.metrics.errors++;
      
      const processingTime = Date.now() - startTime;
      
      return {
        success: false,
        error: error.message,
        thoughtId,
        metrics: {
          processingTimeMs: processingTime
        }
      };
    }
  }

  async updateSessionActivity(sessionId) {
    const sessionKey = `${this.instanceId}:session:${sessionId}`;
    const now = Date.now();
    
    await this.redis.sendCommand([
      'JSON.SET',
      sessionKey,
      '$.lastActivity',
      now.toString()
    ]);
  }

  async publishThoughtEvent(thoughtData) {
    const event = {
      type: 'thought.processed',
      thoughtId: thoughtData.thoughtId,
      sessionId: thoughtData.metadata.sessionId,
      instanceId: thoughtData.metadata.instanceId,
      mode: thoughtData.mode,
      significance: thoughtData.significance,
      timestamp: thoughtData.metadata.timestamp
    };
    
    await this.pubClient.publish(
      'ui:events:thoughts',
      JSON.stringify(event)
    );
  }

  async detectPatterns(sessionId, currentThought) {
    const patterns = [];
    
    // Get recent thoughts from the session
    const streamKey = `${this.instanceId}:thoughts`;
    const recentThoughts = await this.redis.xRevRange(
      streamKey,
      '+',
      '-',
      { COUNT: 10 }
    );
    
    if (recentThoughts.length < 3) {
      return patterns; // Need at least 3 thoughts for pattern detection
    }
    
    // Mode patterns
    const modeCounts = {};
    for (const thought of recentThoughts) {
      const mode = thought.message.mode;
      modeCounts[mode] = (modeCounts[mode] || 0) + 1;
    }
    
    // Check for mode patterns
    for (const [mode, count] of Object.entries(modeCounts)) {
      if (count >= 3) {
        patterns.push({
          type: 'mode_pattern',
          pattern: `Consistent ${mode} mode`,
          confidence: count / recentThoughts.length,
          data: { mode, count, total: recentThoughts.length }
        });
      }
    }
    
    // Significance patterns
    const significances = recentThoughts.map(t => 
      parseFloat(t.message.significance)
    );
    const avgSignificance = significances.reduce((a, b) => a + b, 0) / significances.length;
    
    if (avgSignificance > 7) {
      patterns.push({
        type: 'high_significance',
        pattern: 'High significance thought cluster',
        confidence: 0.8,
        data: { avgSignificance, count: significances.length }
      });
    }
    
    // Tag patterns
    const tagFrequency = {};
    for (const thought of recentThoughts) {
      const tags = JSON.parse(thought.message.tags || '[]');
      for (const tag of tags) {
        tagFrequency[tag] = (tagFrequency[tag] || 0) + 1;
      }
    }
    
    // Find recurring tags
    for (const [tag, count] of Object.entries(tagFrequency)) {
      if (count >= 3) {
        patterns.push({
          type: 'tag_pattern',
          pattern: `Recurring tag: ${tag}`,
          confidence: count / recentThoughts.length,
          data: { tag, count, total: recentThoughts.length }
        });
      }
    }
    
    // Time-based patterns
    const timestamps = recentThoughts.map(t => 
      parseInt(t.id.split('-')[0])
    );
    
    const intervals = [];
    for (let i = 1; i < timestamps.length; i++) {
      intervals.push(timestamps[i-1] - timestamps[i]);
    }
    
    if (intervals.length > 0) {
      const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      if (avgInterval < 30000) { // Less than 30 seconds average
        patterns.push({
          type: 'rapid_thinking',
          pattern: 'Rapid thought generation',
          confidence: 0.7,
          data: { avgIntervalMs: avgInterval, thoughtCount: recentThoughts.length }
        });
      }
    }
    
    return patterns;
  }

  async applyFramework(sessionId, frameworkKey, thoughtId) {
    try {
      const framework = this.frameworkEngine.startFramework(
        sessionId,
        frameworkKey,
        thoughtId
      );
      
      return {
        applied: true,
        framework: frameworkKey,
        sessionKey: framework.sessionKey,
        status: 'started'
      };
    } catch (error) {
      console.error(`Error applying framework ${frameworkKey}:`, error);
      return {
        applied: false,
        framework: frameworkKey,
        error: error.message
      };
    }
  }

  async cacheResult(thoughtId, result) {
    const cacheKey = `${this.instanceId}:cache:thought:${thoughtId}`;
    await this.redis.set(
      cacheKey,
      JSON.stringify(result),
      { EX: 300 } // 5 minutes TTL
    );
  }

  async getCachedResult(thoughtId) {
    const cacheKey = `${this.instanceId}:cache:thought:${thoughtId}`;
    const cached = await this.redis.get(cacheKey);
    return cached ? JSON.parse(cached) : null;
  }

  async getMetrics() {
    const avgProcessingTime = this.metrics.thoughtsProcessed > 0
      ? this.metrics.totalProcessingTime / this.metrics.thoughtsProcessed
      : 0;
    
    return {
      thoughtsProcessed: this.metrics.thoughtsProcessed,
      avgProcessingTimeMs: Math.round(avgProcessingTime),
      totalProcessingTimeMs: this.metrics.totalProcessingTime,
      errors: this.metrics.errors,
      errorRate: this.metrics.thoughtsProcessed > 0
        ? this.metrics.errors / this.metrics.thoughtsProcessed
        : 0
    };
  }

  async reset() {
    this.metrics = {
      thoughtsProcessed: 0,
      totalProcessingTime: 0,
      errors: 0
    };
  }
}