# UnifiedMind MCP

A cognitive subconscious platform for pattern learning and adaptive dialogue, built as an MCP (Model Context Protocol) service.

## Architecture

UnifiedMind provides a subconscious processing layer that:
- Learns from patterns in interactions
- Suggests optimal retrieval strategies
- Engages in internal dialogue processing
- Monitors cognitive performance

### Components

1. **Pattern Engine** - Identifies and learns from recurring patterns
2. **Retrieval Learner** - Optimizes information retrieval strategies
3. **Dialogue Manager** - Processes internal cognitive dialogue
4. **Cognitive Monitor** - Tracks performance and learning outcomes

## Building

```bash
cargo build --release
```

## Running

```bash
# Ensure Redis is running
REDIS_URL=redis://127.0.0.1:6379 cargo run
```

## MCP Tools

- `mind_dialogue` - Process internal thoughts and explore patterns
- `mind_pattern_match` - Match contexts against learned patterns
- `mind_suggest_retrieval` - Get optimal retrieval strategy suggestions
- `mind_learn_outcome` - Record task outcomes for continuous learning

## Environment Variables

- `REDIS_URL` - Redis connection URL (default: `redis://127.0.0.1:6379`)
- `RUST_LOG` - Logging configuration (default: `unified_mind=debug,rmcp=info`)