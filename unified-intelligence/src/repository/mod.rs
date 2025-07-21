mod traits;
mod redis_impl;

#[cfg(test)]
mod test_mock;

// Re-export the traits
pub use traits::{
    ThoughtStorage,
    ThoughtSearch,
    EnhancedSearch,
    ChainOperations,
    FeedbackOperations,
    IdentityOperations,
    IdentityDocumentOperations,
    EventOperations,
    Repository,
};

// Re-export the implementation
pub use redis_impl::RedisRepository;

// For backwards compatibility, keep ThoughtRepository as an alias

// Re-export test mock
#[cfg(test)]
pub use test_mock::MockRepository;