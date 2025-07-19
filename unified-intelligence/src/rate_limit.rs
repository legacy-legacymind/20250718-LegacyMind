use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{Duration, Instant};
use crate::error::{UnifiedIntelligenceError, Result};

/// Simple in-memory rate limiter for protecting against runaway processes
#[derive(Clone)]
pub struct RateLimiter {
    /// Map of instance_id to their request timestamps
    windows: Arc<Mutex<HashMap<String, Vec<Instant>>>>,
    /// Maximum requests allowed per window
    max_requests: usize,
    /// Time window duration
    window_duration: Duration,
}

impl RateLimiter {
    /// Create a new rate limiter
    /// 
    /// # Arguments
    /// * `max_requests` - Maximum number of requests allowed per window
    /// * `window_seconds` - Duration of the sliding window in seconds
    pub fn new(max_requests: usize, window_seconds: u64) -> Self {
        Self {
            windows: Arc::new(Mutex::new(HashMap::new())),
            max_requests,
            window_duration: Duration::from_secs(window_seconds),
        }
    }
    
    /// Check if an instance is allowed to make a request
    /// 
    /// # Arguments
    /// * `instance_id` - The instance identifier to check
    /// 
    /// # Returns
    /// * `Ok(())` if the request is allowed
    /// * `Err(UnifiedIntelligenceError::RateLimit)` if rate limit exceeded
    pub async fn check_rate_limit(&self, instance_id: &str) -> Result<()> {
        let mut windows = self.windows.lock().await;
        let now = Instant::now();
        
        // Get or create the window for this instance
        let timestamps = windows.entry(instance_id.to_string()).or_insert_with(Vec::new);
        
        // Remove timestamps outside the window
        timestamps.retain(|&timestamp| now.duration_since(timestamp) < self.window_duration);
        
        // Check if we're at the limit
        if timestamps.len() >= self.max_requests {
            tracing::warn!(
                "Rate limit exceeded for instance '{}': {} requests in {:?}", 
                instance_id, 
                timestamps.len(),
                self.window_duration
            );
            return Err(UnifiedIntelligenceError::RateLimit);
        }
        
        // Add the current timestamp
        timestamps.push(now);
        
        Ok(())
    }
    
    /// Get current usage statistics for monitoring
    #[allow(dead_code)]
    pub async fn get_usage_stats(&self) -> HashMap<String, usize> {
        let mut windows = self.windows.lock().await;
        let now = Instant::now();
        let mut stats = HashMap::new();
        
        // Clean up old entries and collect stats
        for (instance_id, timestamps) in windows.iter_mut() {
            timestamps.retain(|&timestamp| now.duration_since(timestamp) < self.window_duration);
            if !timestamps.is_empty() {
                stats.insert(instance_id.clone(), timestamps.len());
            }
        }
        
        // Remove instances with no recent activity
        windows.retain(|_, timestamps| !timestamps.is_empty());
        
        stats
    }
    
    /// Clear rate limit data for a specific instance (useful for testing or admin override)
    #[allow(dead_code)]
    pub async fn clear_instance(&self, instance_id: &str) {
        let mut windows = self.windows.lock().await;
        windows.remove(instance_id);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_rate_limiter_allows_requests_under_limit() {
        let limiter = RateLimiter::new(5, 60); // 5 requests per minute
        
        // Should allow 5 requests
        for i in 0..5 {
            assert!(
                limiter.check_rate_limit("test-instance").await.is_ok(),
                "Request {} should be allowed", i + 1
            );
        }
    }
    
    #[tokio::test]
    async fn test_rate_limiter_blocks_over_limit() {
        let limiter = RateLimiter::new(3, 60); // 3 requests per minute
        
        // Allow first 3 requests
        for _ in 0..3 {
            assert!(limiter.check_rate_limit("test-instance").await.is_ok());
        }
        
        // 4th request should be blocked
        assert!(
            matches!(
                limiter.check_rate_limit("test-instance").await,
                Err(UnifiedIntelligenceError::RateLimit)
            ),
            "4th request should be rate limited"
        );
    }
    
    #[tokio::test]
    async fn test_rate_limiter_different_instances() {
        let limiter = RateLimiter::new(2, 60); // 2 requests per minute
        
        // Instance A uses its limit
        assert!(limiter.check_rate_limit("instance-a").await.is_ok());
        assert!(limiter.check_rate_limit("instance-a").await.is_ok());
        assert!(limiter.check_rate_limit("instance-a").await.is_err());
        
        // Instance B should still be allowed
        assert!(limiter.check_rate_limit("instance-b").await.is_ok());
        assert!(limiter.check_rate_limit("instance-b").await.is_ok());
        assert!(limiter.check_rate_limit("instance-b").await.is_err());
    }
    
    #[tokio::test]
    async fn test_sliding_window() {
        let limiter = RateLimiter::new(2, 1); // 2 requests per second
        
        // Use up the limit
        assert!(limiter.check_rate_limit("test").await.is_ok());
        assert!(limiter.check_rate_limit("test").await.is_ok());
        assert!(limiter.check_rate_limit("test").await.is_err());
        
        // Wait for window to pass
        tokio::time::sleep(Duration::from_millis(1100)).await;
        
        // Should be allowed again
        assert!(limiter.check_rate_limit("test").await.is_ok());
    }
}