# Integrated Monitoring System

The Unified Mind monitoring system orchestrates three key components to provide intelligent conversation monitoring and intervention generation.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CognitiveMonitor                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌────────────────┐  ┌─────────────┐ │
│  │ConversationTracker│  │ EntityDetector  │  │FlowAnalyzer │ │
│  └──────────────────┘  └────────────────┘  └─────────────┘ │
│           │                     │                    │       │
│           └─────────────────────┴────────────────────┘       │
│                               │                              │
│                    ┌─────────────────────┐                   │
│                    │ Intervention Queue  │                   │
│                    └─────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Conversation Stream Monitoring
- Monitors Redis streams matching pattern `conversation:{instance}:{session}`
- Processes messages in real-time through all three analyzers
- Maintains conversation context and history

### 2. Multi-Analyzer Processing
Each conversation message is analyzed by:

**ConversationTracker**
- Tracks conversation sessions and participants
- Maintains message history and context
- Calculates conversation velocity and patterns

**EntityDetector**
- Identifies technical terms, code elements, and domain entities
- Determines enrichment needs for detected entities
- Tracks entity trends over time

**FlowAnalyzer**
- Monitors conversation state (Exploring, Focused, Stuck, Transitioning)
- Detects when interventions are needed
- Provides flow-based recommendations

### 3. Intelligent Intervention Generation

The system generates interventions based on:
- **Flow State**: Stuck conversations trigger assistance
- **Entity Detection**: Important entities trigger enrichment
- **Pattern Recognition**: Detected patterns suggest applications
- **Cognitive Load**: High load or fatigue triggers warnings
- **Complexity**: Complex messages trigger framework suggestions

### 4. Intervention Types

```rust
pub enum InterventionType {
    MemoryRetrieval,       // Fetch relevant context
    FrameworkSuggestion,   // Suggest thinking frameworks
    UncertaintyAssistance, // Help with unclear situations
    CognitiveFatigueWarning, // Warn about fatigue
    PatternRecognition,    // Apply detected patterns
    ContextSwitchHelp,     // Assist with context changes
    FocusRedirection,      // Guide attention focus
}
```

### 5. Enhanced Intervention Execution

Interventions are enriched with:
- Conversation context from the tracker
- Entity information for better retrieval
- Flow state for contextual suggestions
- Pattern analysis for relevant applications

## Usage Example

```rust
// Initialize monitor
let monitor = CognitiveMonitor::new(
    redis_conn,
    pattern_engine,
    retrieval_learner,
    dialogue_manager,
).await?;

// Start monitoring
monitor.start_monitoring().await?;

// Monitor will automatically:
// 1. Subscribe to conversation streams
// 2. Process messages through analyzers
// 3. Generate interventions
// 4. Queue them for processing

// Get status
let status = monitor.get_monitoring_status().await?;

// Get insights
let insights = monitor.get_monitoring_insights().await?;
```

## Monitoring Status

The system provides comprehensive status including:
- Cognitive state metrics
- Conversation tracking statistics
- Flow analysis state
- Entity detection metrics
- Component health status
- Intervention queue size

## Health Monitoring

A background health checker runs every 30 seconds to:
- Monitor component status
- Track queue sizes
- Detect backlogs
- Store health metrics in Redis

## Best Practices

1. **Initialize Components**: Call `initialize_monitoring_components()` during startup
2. **Monitor Health**: Check component health regularly via status endpoint
3. **Process Interventions**: Ensure intervention queue doesn't grow too large
4. **Track Metrics**: Use insights API to understand conversation patterns
5. **Handle Shutdowns**: Call `shutdown()` to save final state

## Integration Points

The monitoring system integrates with:
- **Pattern Engine**: For pattern detection and application
- **Retrieval Learner**: For context enrichment
- **Dialogue Manager**: For generating assistance
- **Redis Streams**: For real-time message processing
- **Redis Pub/Sub**: For intervention events