export class FederationHandler {
  constructor(redisClient) {
    this.redis = redisClient;
    this.consumerGroup = 'federation-consumers';
    this.consumerId = `consumer-${Date.now()}`;
  }

  async initializeConsumerGroup(streamKey) {
    try {
      await this.redis.xGroupCreate(streamKey, this.consumerGroup, '$');
    } catch (err) {
      if (!err.message.includes('BUSYGROUP')) {
        throw err;
      }
      // Group already exists
    }
  }

  async shareFederationInsight(fromInstance, toInstance, insight) {
    const streamKey = `federation:stream:${toInstance}`;
    
    // Ensure consumer group exists
    await this.initializeConsumerGroup(streamKey);
    
    // Add message to stream
    const messageId = await this.redis.xAdd(
      streamKey,
      '*',
      {
        from: fromInstance,
        type: 'insight',
        content: JSON.stringify(insight),
        timestamp: Date.now().toString()
      },
      { MAXLEN: { strategy: 'APPROX', threshold: 1000 } }
    );
    
    // Publish notification
    await this.redis.publish(`federation:notify:${toInstance}`, JSON.stringify({
      from: fromInstance,
      messageId,
      type: 'insight'
    }));
    
    return { success: true, messageId };
  }

  async processFederationMessages(instanceId) {
    const streamKey = `federation:stream:${instanceId}`;
    
    // Read messages with consumer group
    const messages = await this.redis.xReadGroup(
      this.consumerGroup,
      this.consumerId,
      { key: streamKey, id: '>' }, // Read only new messages
      { COUNT: 10, BLOCK: 5000 }
    );
    
    if (!messages || messages.length === 0) {
      return [];
    }
    
    const processed = [];
    
    for (const message of messages[0].messages) {
      try {
        const data = {
          id: message.id,
          from: message.message.from,
          type: message.message.type,
          content: JSON.parse(message.message.content),
          timestamp: parseInt(message.message.timestamp)
        };
        
        // Process the message
        processed.push(data);
        
        // Acknowledge the message
        await this.redis.xAck(streamKey, this.consumerGroup, message.id);
      } catch (err) {
        console.error(`Error processing federation message ${message.id}:`, err);
        // Message will be retried by another consumer
      }
    }
    
    return processed;
  }

  async getPendingMessages(instanceId) {
    const streamKey = `federation:stream:${instanceId}`;
    
    // Get pending messages for this consumer group
    const pending = await this.redis.xPending(
      streamKey,
      this.consumerGroup,
      { start: '-', end: '+', count: 100 }
    );
    
    return pending;
  }

  async claimStaleMessages(instanceId, staleTimeout = 300000) {
    const streamKey = `federation:stream:${instanceId}`;
    const pending = await this.getPendingMessages(instanceId);
    
    const claimed = [];
    
    for (const msg of pending) {
      if (msg.millisecondsSinceLastDelivery > staleTimeout) {
        try {
          const messages = await this.redis.xClaim(
            streamKey,
            this.consumerGroup,
            this.consumerId,
            staleTimeout,
            [msg.id]
          );
          
          if (messages.length > 0) {
            claimed.push(messages[0]);
          }
        } catch (err) {
          console.error(`Error claiming message ${msg.id}:`, err);
        }
      }
    }
    
    return claimed;
  }

  async getFederationContext(instanceId, options = {}) {
    const { includeShared = true, limit = 50 } = options;
    
    const streamKey = `federation:stream:${instanceId}`;
    
    // Get recent processed messages
    const messages = await this.redis.xRevRange(streamKey, '+', '-', { COUNT: limit });
    
    const context = {
      instanceId,
      sharedInsights: [],
      receivedInsights: []
    };
    
    for (const message of messages) {
      const data = {
        id: message.id,
        from: message.message.from,
        type: message.message.type,
        content: JSON.parse(message.message.content),
        timestamp: parseInt(message.message.timestamp)
      };
      
      if (data.from === instanceId) {
        context.sharedInsights.push(data);
      } else {
        context.receivedInsights.push(data);
      }
    }
    
    return context;
  }
}