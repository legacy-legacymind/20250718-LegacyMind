use std::collections::HashSet;
use strsim::levenshtein;
use rust_stemmers::{Algorithm, Stemmer};
use crate::models::ThoughtRecord;

/// Search enhancement utilities for improving text-based search without embeddings
pub struct SearchEnhancer {
    stemmer: Stemmer,
}

impl SearchEnhancer {
    pub fn new() -> Self {
        Self {
            stemmer: Stemmer::create(Algorithm::English),
        }
    }

    /// Enhanced search that combines multiple text-based techniques
    pub fn search_enhanced(
        &self,
        thoughts: &[ThoughtRecord],
        query: &str,
        limit: usize,
    ) -> Vec<ThoughtRecord> {
        let processed_query = self.preprocess_query(query);
        let query_terms = self.extract_terms(&processed_query);
        let query_stems = self.stem_terms(&query_terms);

        let mut scored_thoughts: Vec<(f64, &ThoughtRecord)> = thoughts
            .iter()
            .filter_map(|thought| {
                let score = self.calculate_relevance_score(thought, &processed_query, &query_terms, &query_stems);
                // Only include results with meaningful scores (minimum threshold)
                if score >= 0.5 {
                    Some((score, thought))
                } else {
                    None
                }
            })
            .collect();

        // Sort by score descending
        scored_thoughts.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

        // Return top results
        scored_thoughts
            .into_iter()
            .take(limit)
            .map(|(_, thought)| thought.clone())
            .collect()
    }

    /// Preprocess query for better matching
    fn preprocess_query(&self, query: &str) -> String {
        query
            .to_lowercase()
            .chars()
            .filter(|c| c.is_alphanumeric() || c.is_whitespace())
            .collect::<String>()
            .split_whitespace()
            .collect::<Vec<&str>>()
            .join(" ")
    }

    /// Extract individual terms from text
    fn extract_terms(&self, text: &str) -> Vec<String> {
        text.split_whitespace()
            .filter(|term| term.len() > 1) // Filter out single characters
            .map(|term| term.to_string())
            .collect()
    }

    /// Apply stemming to terms for better word variant matching
    fn stem_terms(&self, terms: &[String]) -> Vec<String> {
        terms
            .iter()
            .map(|term| self.stemmer.stem(term).to_string())
            .collect()
    }

    /// Calculate relevance score using multiple techniques
    fn calculate_relevance_score(
        &self,
        thought: &ThoughtRecord,
        processed_query: &str,
        query_terms: &[String],
        query_stems: &[String],
    ) -> f64 {
        let content = thought.content.to_lowercase();
        let mut score = 0.0;

        // 1. Exact phrase matching (highest weight)
        if content.contains(processed_query) {
            score += 10.0;
        }

        // 2. Exact term matching
        let content_words: HashSet<String> = content
            .split_whitespace()
            .map(|s| s.to_string())
            .collect();

        let exact_matches = query_terms
            .iter()
            .filter(|term| content_words.contains(*term))
            .count();

        score += exact_matches as f64 * 3.0;

        // 3. Stemmed term matching
        let content_stems: HashSet<String> = content_words
            .iter()
            .map(|word| self.stemmer.stem(word).to_string())
            .collect();

        let stem_matches = query_stems
            .iter()
            .filter(|stem| content_stems.contains(*stem))
            .count();

        score += stem_matches as f64 * 2.0;

        // 4. Fuzzy matching for typo tolerance
        let fuzzy_matches = query_terms
            .iter()
            .map(|query_term| {
                content_words
                    .iter()
                    .map(|content_word| {
                        let distance = levenshtein(query_term, content_word);
                        let max_len = query_term.len().max(content_word.len());
                        if max_len > 0 && distance as f64 / max_len as f64 <= 0.3 {
                            // Allow up to 30% character difference
                            1.0 - (distance as f64 / max_len as f64)
                        } else {
                            0.0
                        }
                    })
                    .fold(0.0, f64::max)
            })
            .sum::<f64>();

        score += fuzzy_matches;

        // 5. Substring matching for partial word searches
        let substring_matches = query_terms
            .iter()
            .filter(|term| {
                term.len() >= 3 && content_words.iter().any(|word| {
                    word.contains(*term) || term.contains(word)
                })
            })
            .count();

        score += substring_matches as f64 * 0.5;

        // 6. Bonus for recent thoughts (recency bias)
        if let Ok(created_at) = chrono::DateTime::parse_from_rfc3339(&thought.timestamp) {
            let now = chrono::Utc::now();
            let created_at_utc = created_at.with_timezone(&chrono::Utc);
            let age_hours = (now - created_at_utc).num_hours() as f64;
            
            // Apply recency bonus that decays over time
            if age_hours < 24.0 {
                score += 2.0 * (1.0 - age_hours / 24.0);
            } else if age_hours < 168.0 { // 1 week
                score += 1.0 * (1.0 - age_hours / 168.0);
            }
        }

        score
    }

    /// Filter thoughts that meet minimum relevance threshold
    pub fn filter_by_relevance_threshold(
        &self,
        thoughts: &[ThoughtRecord],
        query: &str,
        threshold: f64,
    ) -> Vec<ThoughtRecord> {
        let processed_query = self.preprocess_query(query);
        let query_terms = self.extract_terms(&processed_query);
        let query_stems = self.stem_terms(&query_terms);

        thoughts
            .iter()
            .filter(|thought| {
                let score = self.calculate_relevance_score(thought, &processed_query, &query_terms, &query_stems);
                score >= threshold
            })
            .cloned()
            .collect()
    }
}

impl Default for SearchEnhancer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::ThoughtRecord;

    fn create_test_thought(content: &str, timestamp: &str) -> ThoughtRecord {
        ThoughtRecord {
            id: "test-id".to_string(),
            instance: "test".to_string(),
            thought: content.to_string(),
            content: content.to_string(),
            thought_number: 1,
            total_thoughts: 1,
            timestamp: timestamp.to_string(),
            chain_id: None,
            next_thought_needed: false,
            similarity: None,
        }
    }

    #[test]
    fn test_exact_phrase_matching() {
        let enhancer = SearchEnhancer::new();
        let thoughts = vec![
            create_test_thought("Redis performance optimization", "2025-07-20T15:00:00Z"),
            create_test_thought("Database indexing strategies", "2025-07-20T15:00:00Z"),
        ];

        let results = enhancer.search_enhanced(&thoughts, "Redis performance", 10);
        assert_eq!(results.len(), 1);
        assert!(results[0].content.contains("Redis performance"));
    }

    #[test]
    fn test_fuzzy_matching() {
        let enhancer = SearchEnhancer::new();
        let thoughts = vec![
            create_test_thought("Redis configuration settings", "2025-07-20T15:00:00Z"),
        ];

        // Test with typo: "Rediss" instead of "Redis"
        let results = enhancer.search_enhanced(&thoughts, "Rediss config", 10);
        assert_eq!(results.len(), 1);
    }

    #[test]
    fn test_stemming() {
        let enhancer = SearchEnhancer::new();
        let thoughts = vec![
            create_test_thought("Running performance tests", "2025-07-20T15:00:00Z"),
        ];

        // "run" should match "running" through stemming
        let results = enhancer.search_enhanced(&thoughts, "run performance", 10);
        assert_eq!(results.len(), 1);
    }

    #[test]
    fn test_substring_matching() {
        let enhancer = SearchEnhancer::new();
        let thoughts = vec![
            create_test_thought("Implementation details", "2025-07-20T15:00:00Z"),
        ];

        // "impl" should match "Implementation" as substring
        let results = enhancer.search_enhanced(&thoughts, "impl", 10);
        assert_eq!(results.len(), 1);
    }
}