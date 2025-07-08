/**
 * Auto-Capture Monitor - The "Proactive Mind"
 * 
 * Per-instance auto-capture that starts when an instance checks in
 * and continuously monitors for thoughts to capture automatically.
 */

export class AutoCaptureMonitor {
  constructor(redisManager, thoughtRecorder, sessionManager) {
    this.redis = redisManager.getClient();
    this.pubClient = redisManager.getPubClient();
    this.subClient = redisManager.getSubClient();
    this.thoughtRecorder = thoughtRecorder;
    this.sessionManager = sessionManager;
    
    // Track active monitors per instance
    this.activeMonitors = new Map();
    
    // Monitor state
    this.isMonitoring = false;
  }

  /**
   * Start auto-capture for a specific instance
   * Called when instance does check_in
   */
  async startAutoCapture(instanceId, sessionId) {
    if (this.activeMonitors.has(instanceId)) {
      console.log(`Auto-capture already active for instance ${instanceId}`);
      return { success: true, status: 'already_active' };
    }

    console.log(`Starting auto-capture for instance ${instanceId}`);
    
    // Create monitor state for this instance
    const monitorState = {
      instanceId,
      sessionId,
      startTime: Date.now(),
      thoughtsCaptured: 0,
      lastActivity: Date.now(),
      active: true
    };

    this.activeMonitors.set(instanceId, monitorState);

    // Store monitor state in Redis
    await this.redis.sendCommand([
      'JSON.SET',
      `${instanceId}:monitor:state`,
      '$',
      JSON.stringify(monitorState)
    ]);

    // Subscribe to instance-specific channels
    await this.subscribeToInstanceChannels(instanceId);

    // Start the monitor loop if not already running
    if (!this.isMonitoring) {
      this.startMonitorLoop();
    }

    return {
      success: true,
      status: 'started',
      instanceId,
      sessionId,
      monitorState
    };
  }

  /**
   * Stop auto-capture for a specific instance
   */
  async stopAutoCapture(instanceId) {
    const monitorState = this.activeMonitors.get(instanceId);
    if (!monitorState) {
      return { success: false, message: 'No active monitor for instance' };
    }

    console.log(`Stopping auto-capture for instance ${instanceId}`);
    
    // Mark as inactive
    monitorState.active = false;
    monitorState.endTime = Date.now();

    // Update Redis state
    await this.redis.sendCommand([
      'JSON.SET',
      `${instanceId}:monitor:state`,
      '$',
      JSON.stringify(monitorState)
    ]);

    // Unsubscribe from channels
    await this.unsubscribeFromInstanceChannels(instanceId);

    // Remove from active monitors
    this.activeMonitors.delete(instanceId);

    return {
      success: true,
      instanceId,
      finalState: monitorState
    };
  }

  /**
   * Subscribe to Redis channels for instance-specific events
   */
  async subscribeToInstanceChannels(instanceId) {
    const channels = [
      `${instanceId}:thoughts:capture`,
      `${instanceId}:context:update`,
      `${instanceId}:activity:ping`
    ];

    for (const channel of channels) {
      await this.subClient.subscribe(channel, (message, channel) => {
        this.handleInstanceEvent(instanceId, channel, message);
      });
    }
  }

  /**
   * Unsubscribe from instance channels
   */
  async unsubscribeFromInstanceChannels(instanceId) {
    const channels = [
      `${instanceId}:thoughts:capture`,
      `${instanceId}:context:update`, 
      `${instanceId}:activity:ping`
    ];

    for (const channel of channels) {
      await this.subClient.unsubscribe(channel);
    }
  }

  /**
   * Handle events from instance channels
   */
  async handleInstanceEvent(instanceId, channel, message) {
    const monitorState = this.activeMonitors.get(instanceId);
    if (!monitorState || !monitorState.active) {
      return;
    }

    try {
      const eventData = JSON.parse(message);
      
      switch (channel.split(':')[2]) { // Get event type from channel name
        case 'capture':
          await this.handleThoughtCaptureEvent(instanceId, eventData);
          break;
        case 'update':
          await this.handleContextUpdateEvent(instanceId, eventData);
          break;
        case 'ping':
          await this.handleActivityPing(instanceId, eventData);
          break;
      }

      // Update last activity
      monitorState.lastActivity = Date.now();
      
    } catch (error) {
      console.error(`Error handling event for ${instanceId}:`, error);
    }
  }

  /**
   * Handle automatic thought capture events
   */
  async handleThoughtCaptureEvent(instanceId, eventData) {
    const monitorState = this.activeMonitors.get(instanceId);
    if (!monitorState) return;

    console.log(`Auto-capturing thought for ${instanceId}:`, eventData.content?.substring(0, 50) + '...');
    
    try {
      // Get current session for the instance
      const session = await this.sessionManager.getCurrentSession(instanceId);
      if (!session) {
        console.warn(`No active session found for instance ${instanceId}`);
        return;
      }

      // Automatically capture the thought
      const thoughtData = {
        thoughtId: eventData.thoughtId || `auto-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        content: eventData.content,
        mode: eventData.mode || 'auto',
        significance: eventData.significance || 5,
        tags: [...(eventData.tags || []), 'auto-captured'],
        confidence: eventData.confidence || 0.8,
        metadata: {
          instanceId,
          sessionId: session.sessionId,
          autoCapture: true,
          captureTime: Date.now(),
          ...eventData.metadata
        }
      };

      // Record the thought
      await this.thoughtRecorder.recordThought(session.sessionId, thoughtData);
      
      // Update monitor stats
      monitorState.thoughtsCaptured++;
      
      // Publish capture confirmation
      await this.pubClient.publish(`${instanceId}:monitor:captured`, JSON.stringify({
        thoughtId: thoughtData.thoughtId,
        sessionId: session.sessionId,
        captureTime: Date.now()
      }));

    } catch (error) {
      console.error(`Error auto-capturing thought for ${instanceId}:`, error);
      
      // Publish error event
      await this.pubClient.publish(`${instanceId}:monitor:error`, JSON.stringify({
        error: error.message,
        eventData,
        timestamp: Date.now()
      }));
    }
  }

  /**
   * Handle context update events
   */
  async handleContextUpdateEvent(instanceId, eventData) {
    console.log(`Context updated for ${instanceId}:`, eventData.field || 'bulk update');
    
    // Could trigger additional auto-capture based on context changes
    // For now, just log the activity
  }

  /**
   * Handle activity ping events (keep-alive)
   */
  async handleActivityPing(instanceId, eventData) {
    const monitorState = this.activeMonitors.get(instanceId);
    if (monitorState) {
      monitorState.lastActivity = Date.now();
    }
  }

  /**
   * Main monitor loop - checks for inactive instances and cleanup
   */
  startMonitorLoop() {
    if (this.isMonitoring) return;
    
    this.isMonitoring = true;
    console.log('Starting auto-capture monitor loop');

    const monitorInterval = setInterval(async () => {
      try {
        await this.performMonitorMaintenance();
      } catch (error) {
        console.error('Error in monitor maintenance:', error);
      }

      // Stop loop if no active monitors
      if (this.activeMonitors.size === 0) {
        clearInterval(monitorInterval);
        this.isMonitoring = false;
        console.log('Monitor loop stopped - no active instances');
      }
    }, 30000); // Check every 30 seconds
  }

  /**
   * Perform maintenance tasks
   */
  async performMonitorMaintenance() {
    const now = Date.now();
    const inactivityThreshold = 10 * 60 * 1000; // 10 minutes

    for (const [instanceId, monitorState] of this.activeMonitors) {
      // Check for inactive instances
      if (now - monitorState.lastActivity > inactivityThreshold) {
        console.log(`Instance ${instanceId} inactive for ${(now - monitorState.lastActivity) / 1000}s, stopping auto-capture`);
        await this.stopAutoCapture(instanceId);
        continue;
      }

      // Update Redis state periodically
      await this.redis.sendCommand([
        'JSON.SET',
        `${instanceId}:monitor:state`,
        '$.lastActivity',
        monitorState.lastActivity.toString()
      ]);

      // Publish heartbeat
      await this.pubClient.publish(`${instanceId}:monitor:heartbeat`, JSON.stringify({
        instanceId,
        thoughtsCaptured: monitorState.thoughtsCaptured,
        uptime: now - monitorState.startTime,
        lastActivity: monitorState.lastActivity
      }));
    }
  }

  /**
   * Get monitor status for an instance
   */
  async getMonitorStatus(instanceId) {
    const monitorState = this.activeMonitors.get(instanceId);
    
    if (!monitorState) {
      // Check Redis for historical state
      try {
        const redisState = await this.redis.sendCommand([
          'JSON.GET',
          `${instanceId}:monitor:state`,
          '$'
        ]);
        
        if (redisState) {
          const parsedState = JSON.parse(redisState)[0];
          return {
            active: false,
            lastKnownState: parsedState
          };
        }
      } catch (error) {
        // No historical state found
      }
      
      return { active: false, message: 'No monitor found for instance' };
    }

    return {
      active: true,
      ...monitorState,
      uptime: Date.now() - monitorState.startTime
    };
  }

  /**
   * Get status of all active monitors
   */
  getAllMonitorStatus() {
    const status = {
      totalActiveMonitors: this.activeMonitors.size,
      isMonitoring: this.isMonitoring,
      instances: {}
    };

    for (const [instanceId, monitorState] of this.activeMonitors) {
      status.instances[instanceId] = {
        ...monitorState,
        uptime: Date.now() - monitorState.startTime
      };
    }

    return status;
  }

  /**
   * Manually trigger thought capture for an instance
   */
  async triggerCapture(instanceId, content, options = {}) {
    const eventData = {
      thoughtId: options.thoughtId,
      content,
      mode: options.mode,
      significance: options.significance,
      tags: options.tags,
      confidence: options.confidence,
      metadata: options.metadata
    };

    // Publish to the capture channel
    await this.pubClient.publish(`${instanceId}:thoughts:capture`, JSON.stringify(eventData));
    
    return { success: true, instanceId, triggered: true };
  }

  /**
   * Send activity ping for an instance
   */
  async sendActivityPing(instanceId, data = {}) {
    await this.pubClient.publish(`${instanceId}:activity:ping`, JSON.stringify({
      timestamp: Date.now(),
      ...data
    }));
    
    return { success: true, instanceId, pinged: true };
  }

  /**
   * Cleanup all monitors (for shutdown)
   */
  async cleanup() {
    console.log('Cleaning up auto-capture monitors');
    
    const instanceIds = Array.from(this.activeMonitors.keys());
    
    for (const instanceId of instanceIds) {
      await this.stopAutoCapture(instanceId);
    }
    
    this.isMonitoring = false;
    
    return { success: true, cleanedInstances: instanceIds.length };
  }
}