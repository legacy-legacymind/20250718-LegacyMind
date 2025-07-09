pub struct SignificanceAnalyzer;

impl SignificanceAnalyzer {
    pub async fn analyze(content: &str) -> u8 {
        let lower = content.to_lowercase();
        let mut score = 5; // Base score
        
        // Decision indicators (+3)
        if lower.contains("decision") || lower.contains("decide") || lower.contains("choose") {
            score += 3;
        }
        
        // Problem indicators (+2)
        if lower.contains("issue") || lower.contains("problem") || lower.contains("error") {
            score += 2;
        }
        
        // Breakthrough indicators (+4)
        if lower.contains("breakthrough") || lower.contains("realized") || lower.contains("discovered") {
            score += 4;
        }
        
        // Solution indicators (+3)
        if lower.contains("solution") || lower.contains("solved") || lower.contains("fixed") {
            score += 3;
        }
        
        // Urgency indicators (+2)
        if lower.contains("urgent") || lower.contains("critical") || lower.contains("important") {
            score += 2;
        }
        
        // Question indicators (+1)
        if content.contains('?') {
            score += 1;
        }
        
        // Length factor (longer content might be more significant)
        if content.len() > 200 {
            score += 1;
        }
        
        // Cap at 10
        score.min(10)
    }
}