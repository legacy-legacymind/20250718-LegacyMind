use serde::{Serialize, Deserialize};
use serde_json;

#[derive(Debug, Serialize)]
#[serde(untagged)]
pub enum TestResponse {
    View {
        name: String,
        categories: Vec<&'static str>,
    },
}

fn main() {
    let response = TestResponse::View {
        name: "Test".to_string(),
        categories: vec!["one", "two", "three"],
    };
    
    match serde_json::to_string(&response) {
        Ok(json) => println!("Serialized successfully: {}", json),
        Err(e) => println!("Serialization error: {}", e),
    }
}