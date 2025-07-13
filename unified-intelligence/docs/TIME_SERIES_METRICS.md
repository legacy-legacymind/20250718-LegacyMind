# Time Series Metrics for Thought Tracking

## Overview

The unified-think server now includes time series metrics for tracking thought patterns and usage over time. This feature uses Redis TimeSeries to efficiently store and query thought count metrics per instance.

## Implementation Details

### Key Format
- Time series keys follow the pattern: `ts:{instance}:thought_count`
- Each instance gets its own time series for tracking thought counts

### Configuration
- **Retention**: 24 hours (86400000 milliseconds)
- **Duplicate Policy**: SUM - Multiple thoughts at the same timestamp are summed
- **Labels**: 
  - `instance`: The instance identifier
  - `metric`: "thought_count"

### Methods Added

1. **`init_thought_metrics(instance: &str)`** - src/redis.rs:252
   - Creates a new time series for an instance
   - Automatically called if series doesn't exist
   - Non-blocking - failures are logged but don't stop operation

2. **`increment_thought_count(instance: &str)`** - src/redis.rs:291
   - Increments the thought count by 1
   - Uses server timestamp automatically
   - Auto-initializes series if needed

### Integration Points

The thought count is automatically incremented in:
- **`save_thought()`** - src/repository.rs:115
  - Called whenever a thought is stored
  - Tracks all thoughts: new, merged, and branched

## Usage

### Prerequisites

Ensure Redis has the TimeSeries module installed:
```bash
redis-cli MODULE LIST
```

If not installed, you can add it with:
```bash
# Using Redis Stack (includes TimeSeries)
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack:latest

# Or load the module manually
redis-cli MODULE LOAD /path/to/redistimeseries.so
```

### Querying Metrics

1. **Check if time series exists:**
   ```bash
   redis-cli TS.INFO "ts:YOUR_INSTANCE:thought_count"
   ```

2. **Get all data points:**
   ```bash
   redis-cli TS.RANGE "ts:YOUR_INSTANCE:thought_count" - +
   ```

3. **Get data for last hour:**
   ```bash
   redis-cli TS.RANGE "ts:YOUR_INSTANCE:thought_count" - + AGGREGATION avg 3600000
   ```

4. **Get current thought count:**
   ```bash
   redis-cli TS.GET "ts:YOUR_INSTANCE:thought_count"
   ```

## Testing

Run the test script to verify functionality:
```bash
./test_time_series_simple.sh
```

Or use the Python test:
```bash
python3 test_time_series.py
```

## Error Handling

- Time series operations are non-fatal
- If Redis TimeSeries is not available, the server continues without metrics
- All failures are logged with appropriate warning levels
- Main thought storage is never blocked by metrics failures

## Future Enhancements

Potential additions for comprehensive metrics:
1. Track thought chain lengths
2. Monitor recall frequencies
3. Measure search query patterns
4. Track instance activity periods
5. Add aggregation rules for hourly/daily summaries