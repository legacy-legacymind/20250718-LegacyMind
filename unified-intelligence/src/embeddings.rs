use std::collections::HashMap;
use sha2::{Sha256, Digest};

/// Simple embedding generator for demonstration purposes
/// Creates 384-dimensional embeddings using TF-IDF-inspired approach
pub struct EmbeddingGenerator {
    dimension: usize,
}

impl EmbeddingGenerator {
    pub fn new() -> Self {
        Self {
            dimension: 384,
        }
    }
    
    /// Generate a 384-dimensional embedding for a given text
    pub fn generate(&self, text: &str) -> Vec<f64> {
        // Tokenize the text (simple whitespace splitting)
        let text_lower = text.to_lowercase();
        let tokens: Vec<&str> = text_lower
            .split_whitespace()
            .collect();
        
        // Create term frequency map
        let mut tf_map: HashMap<String, f64> = HashMap::new();
        let total_tokens = tokens.len() as f64;
        
        for token in &tokens {
            *tf_map.entry(token.to_string()).or_insert(0.0) += 1.0;
        }
        
        // Normalize term frequencies
        for freq in tf_map.values_mut() {
            *freq /= total_tokens;
        }
        
        // Initialize embedding vector
        let mut embedding = vec![0.0; self.dimension];
        
        // Use multiple hash functions to distribute features across dimensions
        for (term, tf) in &tf_map {
            // Generate multiple hash values for each term
            for i in 0..4 {
                let mut hasher = Sha256::new();
                hasher.update(format!("{}{}", term, i).as_bytes());
                let hash = hasher.finalize();
                
                // Use first 8 bytes of hash as position indices
                for j in 0..8 {
                    let pos = (hash[j] as usize * 256 + hash[(j + 8) % 32] as usize) % self.dimension;
                    
                    // Apply TF value with some variation based on hash
                    let weight = tf * (1.0 + (hash[(j + 16) % 32] as f64 / 255.0));
                    embedding[pos] += weight;
                }
            }
        }
        
        // Add positional features (beginning, middle, end emphasis)
        let tokens_vec: Vec<String> = tokens.iter().map(|s| s.to_string()).collect();
        self.add_positional_features(&mut embedding, &tokens_vec);
        
        // Add character-level features
        self.add_character_features(&mut embedding, text);
        
        // Normalize the embedding to unit length (for cosine similarity)
        self.normalize_embedding(&mut embedding);
        
        embedding
    }
    
    /// Add positional features to capture word positions
    fn add_positional_features(&self, embedding: &mut Vec<f64>, tokens: &[String]) {
        if tokens.is_empty() {
            return;
        }
        
        let _n_tokens = tokens.len();
        
        // Emphasize beginning tokens (first 20% of dimensions)
        let begin_range = self.dimension / 5;
        for (i, token) in tokens.iter().take(3).enumerate() {
            let mut hasher = Sha256::new();
            hasher.update(format!("BEGIN_{}", token).as_bytes());
            let hash = hasher.finalize();
            let pos = (hash[0] as usize * 256 + hash[1] as usize) % begin_range;
            embedding[pos] += 0.3 * (1.0 - i as f64 / 3.0);
        }
        
        // Emphasize ending tokens (last 20% of dimensions)
        let end_start = self.dimension * 4 / 5;
        let end_range = self.dimension - end_start;
        for (i, token) in tokens.iter().rev().take(3).enumerate() {
            let mut hasher = Sha256::new();
            hasher.update(format!("END_{}", token).as_bytes());
            let hash = hasher.finalize();
            let pos = end_start + (hash[0] as usize * 256 + hash[1] as usize) % end_range;
            embedding[pos] += 0.3 * (1.0 - i as f64 / 3.0);
        }
    }
    
    /// Add character-level features (length, special chars, etc.)
    fn add_character_features(&self, embedding: &mut Vec<f64>, text: &str) {
        // Text length feature (normalized)
        let len_feature = (text.len() as f64 / 1000.0).min(1.0);
        embedding[self.dimension - 1] = len_feature;
        
        // Special character ratios
        let special_chars = text.chars().filter(|c| !c.is_alphanumeric() && !c.is_whitespace()).count() as f64;
        let special_ratio = special_chars / text.len().max(1) as f64;
        embedding[self.dimension - 2] = special_ratio;
        
        // Digit ratio
        let digits = text.chars().filter(|c| c.is_numeric()).count() as f64;
        let digit_ratio = digits / text.len().max(1) as f64;
        embedding[self.dimension - 3] = digit_ratio;
        
        // Capital letter ratio
        let capitals = text.chars().filter(|c| c.is_uppercase()).count() as f64;
        let capital_ratio = capitals / text.len().max(1) as f64;
        embedding[self.dimension - 4] = capital_ratio;
    }
    
    /// Normalize embedding to unit length for cosine similarity
    fn normalize_embedding(&self, embedding: &mut Vec<f64>) {
        let magnitude: f64 = embedding.iter().map(|x| x * x).sum::<f64>().sqrt();
        
        if magnitude > 0.0 {
            for value in embedding.iter_mut() {
                *value /= magnitude;
            }
        }
    }
    
    /// Generate embedding for a query, with slight boosting for better recall
    pub fn generate_query_embedding(&self, query: &str) -> Vec<f64> {
        let mut embedding = self.generate(query);
        
        // Slightly boost all non-zero values for queries to improve recall
        for value in &mut embedding {
            if *value != 0.0 {
                *value *= 1.1;
            }
        }
        
        // Re-normalize after boosting
        self.normalize_embedding(&mut embedding);
        
        embedding
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_embedding_dimension() {
        let generator = EmbeddingGenerator::new();
        let text = "This is a test thought about Rust programming";
        let embedding = generator.generate(text);
        
        assert_eq!(embedding.len(), 384);
    }
    
    #[test]
    fn test_embedding_normalization() {
        let generator = EmbeddingGenerator::new();
        let text = "Normalized vectors should have magnitude 1";
        let embedding = generator.generate(text);
        
        let magnitude: f64 = embedding.iter().map(|x| x * x).sum::<f64>().sqrt();
        assert!((magnitude - 1.0).abs() < 0.001);
    }
    
    #[test]
    fn test_similar_texts_have_similar_embeddings() {
        let generator = EmbeddingGenerator::new();
        
        let text1 = "Machine learning is a subset of artificial intelligence";
        let text2 = "Machine learning is part of AI and artificial intelligence";
        let text3 = "The weather today is sunny and warm";
        
        let emb1 = generator.generate(text1);
        let emb2 = generator.generate(text2);
        let emb3 = generator.generate(text3);
        
        // Calculate cosine similarities
        let sim_12 = cosine_similarity(&emb1, &emb2);
        let sim_13 = cosine_similarity(&emb1, &emb3);
        
        // Similar texts should have higher similarity than dissimilar texts
        assert!(sim_12 > sim_13);
    }
    
    fn cosine_similarity(a: &[f64], b: &[f64]) -> f64 {
        let dot_product: f64 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        dot_product
    }
}