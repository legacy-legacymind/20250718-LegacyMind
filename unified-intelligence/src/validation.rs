use thiserror::Error;
use std::env;

#[derive(Debug, Error)]
pub enum ValidationError {
    #[error("Thought content too long: {actual} chars (max: {max})")]
    ThoughtTooLong { actual: usize, max: usize },
    
    #[error("Invalid chain ID format: {chain_id}")]
    InvalidChainId { chain_id: String },
    
    #[error("Invalid thought number: {number} (must be 1-{max})")]
    InvalidThoughtNumber { number: i32, max: i32 },
    
    #[error("Invalid instance ID: {instance_id}")]
    #[allow(dead_code)]
    InvalidInstanceId { instance_id: String },
    
    #[error("Thought content cannot be empty")]
    EmptyThought,
}

#[derive(Clone)]
pub struct InputValidator {
    max_thought_length: usize,
    max_thoughts_per_chain: i32,
}

impl InputValidator {
    pub fn new() -> Self {
        Self {
            max_thought_length: env::var("MAX_THOUGHT_LENGTH")
                .unwrap_or_else(|_| "10000".to_string())
                .parse()
                .unwrap_or(10000),
            max_thoughts_per_chain: env::var("MAX_THOUGHTS_PER_CHAIN")
                .unwrap_or_else(|_| "1000".to_string())
                .parse()
                .unwrap_or(1000),
        }
    }
    
    pub fn validate_thought_content(&self, content: &str) -> std::result::Result<(), ValidationError> {
        let trimmed = content.trim();
        
        // Check if empty after trimming
        if trimmed.is_empty() {
            return Err(ValidationError::EmptyThought);
        }
        
        // Check length limit
        let length = trimmed.len();
        if length > self.max_thought_length {
            return Err(ValidationError::ThoughtTooLong {
                actual: length,
                max: self.max_thought_length,
            });
        }
        
        Ok(())
    }
    
    pub fn validate_chain_id(&self, chain_id: &str) -> std::result::Result<(), ValidationError> {
        // Allow any non-empty chain_id for flexibility (not just UUIDs)
        if chain_id.is_empty() {
            Err(ValidationError::InvalidChainId {
                chain_id: chain_id.to_string(),
            })
        } else {
            Ok(())
        }
    }
    
    pub fn validate_thought_numbers(&self, number: i32, total: i32) -> std::result::Result<(), ValidationError> {
        // Validate total_thoughts is within bounds
        if total < 1 || total > self.max_thoughts_per_chain {
            return Err(ValidationError::InvalidThoughtNumber {
                number: total,
                max: self.max_thoughts_per_chain,
            });
        }
        
        // Validate thought_number is within bounds
        if number < 1 || number > total {
            return Err(ValidationError::InvalidThoughtNumber {
                number,
                max: total,
            });
        }
        
        Ok(())
    }
    
    #[allow(dead_code)]
    pub fn validate_instance_id(&self, instance_id: &str) -> std::result::Result<(), ValidationError> {
        // Check length bounds
        if instance_id.is_empty() || instance_id.len() > 50 {
            return Err(ValidationError::InvalidInstanceId {
                instance_id: instance_id.to_string(),
            });
        }
        
        // Check for valid characters: alphanumeric + hyphens only
        if !instance_id.chars().all(|c| c.is_alphanumeric() || c == '-') {
            return Err(ValidationError::InvalidInstanceId {
                instance_id: instance_id.to_string(),
            });
        }
        
        // Check for path traversal patterns
        if instance_id.contains("..") || instance_id.contains('/') || instance_id.contains('\\') {
            return Err(ValidationError::InvalidInstanceId {
                instance_id: instance_id.to_string(),
            });
        }
        
        Ok(())
    }
}

impl Default for InputValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_valid_thought_content() {
        let validator = InputValidator::new();
        assert!(validator.validate_thought_content("Valid thought content").is_ok());
    }
    
    #[test]
    fn test_empty_thought_content() {
        let validator = InputValidator::new();
        assert!(matches!(
            validator.validate_thought_content(""),
            Err(ValidationError::EmptyThought)
        ));
        assert!(matches!(
            validator.validate_thought_content("   "),
            Err(ValidationError::EmptyThought)
        ));
    }
    
    #[test]
    fn test_oversized_thought_content() {
        let validator = InputValidator::new();
        let large_content = "x".repeat(10001);
        assert!(matches!(
            validator.validate_thought_content(&large_content),
            Err(ValidationError::ThoughtTooLong { .. })
        ));
    }
    
    #[test]
    fn test_valid_chain_id() {
        let validator = InputValidator::new();
        let valid_uuid = "550e8400-e29b-41d4-a716-446655440000";
        assert!(validator.validate_chain_id(valid_uuid).is_ok());
    }
    
    #[test]
    fn test_invalid_chain_id() {
        let validator = InputValidator::new();
        assert!(matches!(
            validator.validate_chain_id(""),
            Err(ValidationError::InvalidChainId { .. })
        ));
    }
    
    #[test]
    fn test_valid_thought_numbers() {
        let validator = InputValidator::new();
        assert!(validator.validate_thought_numbers(1, 5).is_ok());
        assert!(validator.validate_thought_numbers(5, 5).is_ok());
    }
    
    #[test]
    fn test_invalid_thought_numbers() {
        let validator = InputValidator::new();
        assert!(matches!(
            validator.validate_thought_numbers(0, 5),
            Err(ValidationError::InvalidThoughtNumber { .. })
        ));
        assert!(matches!(
            validator.validate_thought_numbers(6, 5),
            Err(ValidationError::InvalidThoughtNumber { .. })
        ));
        assert!(matches!(
            validator.validate_thought_numbers(1, 0),
            Err(ValidationError::InvalidThoughtNumber { .. })
        ));
    }
    
    #[test]
    fn test_valid_instance_id() {
        let validator = InputValidator::new();
        assert!(validator.validate_instance_id("CC").is_ok());
        assert!(validator.validate_instance_id("instance-123").is_ok());
        assert!(validator.validate_instance_id("MyInstance").is_ok());
    }
    
    #[test]
    fn test_invalid_instance_id() {
        let validator = InputValidator::new();
        assert!(matches!(
            validator.validate_instance_id(""),
            Err(ValidationError::InvalidInstanceId { .. })
        ));
        assert!(matches!(
            validator.validate_instance_id("invalid/path"),
            Err(ValidationError::InvalidInstanceId { .. })
        ));
        assert!(matches!(
            validator.validate_instance_id("../traversal"),
            Err(ValidationError::InvalidInstanceId { .. })
        ));
        assert!(matches!(
            validator.validate_instance_id("special@chars"),
            Err(ValidationError::InvalidInstanceId { .. })
        ));
    }
}