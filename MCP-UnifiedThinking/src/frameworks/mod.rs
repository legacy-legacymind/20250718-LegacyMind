use anyhow::Result;

/// A trait for applying a thinking framework to a piece of content.
pub trait Framework {
    /// Applies the framework's logic to the given content.
    fn apply(&self, content: &str) -> Result<serde_json::Value>;
}

pub mod socratic;
pub mod first_principles;