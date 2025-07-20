#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{Identity, IdentityResponse};
    
    #[test]
    fn test_identity_response_serialization() {
        // Create a minimal identity
        let identity = Identity::default_for_instance("TEST");
        
        // Create the response
        let response = IdentityResponse::View {
            identity,
            available_categories: vec![
                "core_info".to_string(),
                "communication".to_string(),
                "relationships".to_string(),
                "work_preferences".to_string(),
                "behavioral_patterns".to_string(),
                "technical_profile".to_string(),
                "context_awareness".to_string(),
                "memory_preferences".to_string()
            ],
        };
        
        // Try to serialize
        match serde_json::to_string(&response) {
            Ok(json) => {
                println!("Serialized successfully!");
                println!("JSON length: {} bytes", json.len());
            }
            Err(e) => {
                println!("Serialization failed: {}", e);
                panic!("Failed to serialize IdentityResponse: {}", e);
            }
        }
    }
}