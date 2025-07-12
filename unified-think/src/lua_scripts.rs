/// Lua script constants for atomic Redis operations
/// These scripts ensure atomicity and prevent race conditions in multi-step operations

/// Script to atomically store a thought with all associated operations
/// 
/// KEYS[1] = thought key ({instance}/Thoughts/{uuid})
/// KEYS[2] = bloom filter key ({instance}/bloom/thoughts)
/// KEYS[3] = time series key ({instance}/metrics/thought_count)
/// KEYS[4] = chain key ({instance}/chains/{chain_id}) - optional
/// 
/// ARGV[1] = thought JSON data
/// ARGV[2] = thought UUID
/// ARGV[3] = timestamp (epoch seconds)
/// ARGV[4] = chain_id (optional)
/// 
/// Returns: "OK" on success, "DUPLICATE" if already exists
pub const STORE_THOUGHT_SCRIPT: &str = r#"
-- Check if thought already exists
if redis.call('EXISTS', KEYS[1]) == 1 then
    return 'DUPLICATE'
end

-- Check bloom filter for potential duplicate
local bloom_key = KEYS[2]
local uuid = ARGV[2]

-- Check bloom filter using BF.EXISTS
local bloom_exists = redis.call('BF.EXISTS', bloom_key, uuid)
if bloom_exists == 1 then
    -- Potential duplicate, double-check with actual key
    if redis.call('EXISTS', KEYS[1]) == 1 then
        return 'DUPLICATE'
    end
end

-- Store the thought
redis.call('SET', KEYS[1], ARGV[1])

-- Add to bloom filter using BF.ADD
redis.call('BF.ADD', bloom_key, uuid)

-- Update time series metrics
local ts_key = KEYS[3]
local timestamp = tonumber(ARGV[3])
redis.call('TS.ADD', ts_key, timestamp, 1)

-- Add to chain if chain_id is provided
if ARGV[4] and ARGV[4] ~= '' then
    local chain_key = KEYS[4]
    redis.call('RPUSH', chain_key, uuid)
end

return 'OK'
"#;

/// Script to atomically get a thought and update access metrics
/// 
/// KEYS[1] = thought key ({instance}/Thoughts/{uuid})
/// KEYS[2] = access count key ({instance}/metrics/access_count)
/// KEYS[3] = last access key ({instance}/Thoughts/{uuid}:last_access)
/// 
/// ARGV[1] = timestamp (epoch seconds)
/// 
/// Returns: thought JSON or nil if not found
pub const GET_THOUGHT_SCRIPT: &str = r#"
local thought = redis.call('GET', KEYS[1])
if thought == false then
    return nil
end

-- Update access metrics
redis.call('TS.ADD', KEYS[2], ARGV[1], 1)
redis.call('SET', KEYS[3], ARGV[1])

return thought
"#;

/// Script to atomically search thoughts with pagination
/// 
/// KEYS[1] = search index key pattern
/// 
/// ARGV[1] = search query
/// ARGV[2] = offset
/// ARGV[3] = limit
/// 
/// Returns: array of [total_count, thought_json1, thought_json2, ...]
pub const SEARCH_THOUGHTS_SCRIPT: &str = r#"
-- This is a placeholder for full-text search
-- In production, you'd use RediSearch or similar
-- For now, we'll scan keys matching a pattern

-- KEYS[1] = search pattern (e.g., instance/Thoughts/*)
-- ARGV[1] = search query (not used in simple scan)
-- ARGV[2] = offset
-- ARGV[3] = limit

local pattern = KEYS[1]
local cursor = '0'
local all_keys = {}

-- Scan all thought keys
repeat
    local result = redis.call('SCAN', cursor, 'MATCH', pattern, 'COUNT', 1000)
    cursor = result[1]
    for _, key in ipairs(result[2]) do
        table.insert(all_keys, key)
    end
until cursor == '0'

local total = #all_keys
local offset = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Apply pagination
local results = {total}
for i = offset + 1, math.min(offset + limit, total) do
    local thought = redis.call('GET', all_keys[i])
    if thought then
        table.insert(results, thought)
    end
end

return results
"#;

/// Script to atomically update thought chain operations
/// 
/// KEYS[1] = chain key ({instance}/chains/{chain_id})
/// KEYS[2] = thought key ({instance}/Thoughts/{uuid})
/// 
/// ARGV[1] = operation ('add' or 'remove')
/// ARGV[2] = thought UUID
/// 
/// Returns: 1 on success, 0 on failure
pub const UPDATE_CHAIN_SCRIPT: &str = r#"
local operation = ARGV[1]
local uuid = ARGV[2]

-- Verify thought exists
if redis.call('EXISTS', KEYS[2]) == 0 then
    return 0
end

if operation == 'add' then
    -- Check if already in chain
    local chain = redis.call('LRANGE', KEYS[1], 0, -1)
    for _, id in ipairs(chain) do
        if id == uuid then
            return 0  -- Already in chain
        end
    end
    redis.call('RPUSH', KEYS[1], uuid)
elseif operation == 'remove' then
    redis.call('LREM', KEYS[1], 0, uuid)
else
    return 0  -- Invalid operation
end

return 1
"#;

/// Script to get chain thoughts with proper ordering
/// 
/// KEYS[1] = chain key ({instance}/chains/{chain_id})
/// 
/// ARGV[1] = instance (e.g., "Claude")
/// 
/// Returns: array of thought JSONs in chain order
pub const GET_CHAIN_THOUGHTS_SCRIPT: &str = r#"
local chain_ids = redis.call('LRANGE', KEYS[1], 0, -1)
local thoughts = {}

for _, uuid in ipairs(chain_ids) do
    -- Build key using instance from ARGV
    local instance = ARGV[1]
    local thought_key = instance .. '/Thoughts/' .. uuid
    local thought = redis.call('GET', thought_key)
    if thought then
        table.insert(thoughts, thought)
    end
end

return thoughts
"#;

/// Script to cleanup expired data
/// 
/// KEYS[1] = pattern for keys to check (e.g., instance/Thoughts/*)
/// 
/// ARGV[1] = expiration timestamp
/// 
/// Returns: number of keys cleaned up
pub const CLEANUP_EXPIRED_SCRIPT: &str = r#"
local pattern = KEYS[1]
local expire_before = tonumber(ARGV[1])
local cursor = '0'
local cleaned = 0

repeat
    local result = redis.call('SCAN', cursor, 'MATCH', pattern, 'COUNT', 100)
    cursor = result[1]
    
    for _, key in ipairs(result[2]) do
        local thought = redis.call('GET', key)
        if thought then
            -- Parse JSON to check timestamp
            -- In production, use a proper JSON parser
            local ts_start = string.find(thought, '"timestamp":')
            if ts_start then
                local ts_end = string.find(thought, ',', ts_start)
                if ts_end then
                    local ts_str = string.sub(thought, ts_start + 12, ts_end - 1)
                    local ts = tonumber(ts_str)
                    if ts and ts < expire_before then
                        redis.call('DEL', key)
                        cleaned = cleaned + 1
                    end
                end
            end
        end
    end
until cursor == '0'

return cleaned
"#;

/// Structure to hold loaded script SHAs
#[derive(Debug, Clone)]
pub struct LoadedScripts {
    pub store_thought: String,
    pub get_thought: String,
    pub search_thoughts: String,
    pub update_chain: String,
    pub get_chain_thoughts: String,
    pub cleanup_expired: String,
}

impl LoadedScripts {
    pub fn new() -> Self {
        Self {
            store_thought: String::new(),
            get_thought: String::new(),
            search_thoughts: String::new(),
            update_chain: String::new(),
            get_chain_thoughts: String::new(),
            cleanup_expired: String::new(),
        }
    }
}