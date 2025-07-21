use regex::Regex;
use serde::{Deserialize, Serialize};
use schemars::JsonSchema;
use std::path::PathBuf;
use once_cell::sync::Lazy;
use urlencoding::encode;

/// A wikilink found in content
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct Wikilink {
    /// The raw wikilink text as it appears in content (e.g., "[[Note Name|Display]]")
    pub raw_text: String,
    /// The target file or note name (e.g., "Note Name" or "folder/Note Name")
    pub target_file: String,
    /// Optional display text if provided (e.g., "Display" from [[Note|Display]])
    pub display_text: Option<String>,
    /// Generated obsidian:// URL for opening the target file
    pub obsidian_url: String,
    /// Whether the target file exists in the vault
    pub is_valid: bool,
    /// Resolved absolute path if target file exists
    pub resolved_path: Option<String>,
    /// Character position where the wikilink starts in the content
    pub start_pos: usize,
    /// Character position where the wikilink ends in the content
    pub end_pos: usize,
}

/// Summary of wikilinks found in content
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct WikilinkSummary {
    /// Total number of wikilinks found
    pub total_count: usize,
    /// Number of valid wikilinks (target files exist)
    pub valid_count: usize,
    /// Number of broken wikilinks (target files don't exist)
    pub broken_count: usize,
    /// All wikilinks found in the content
    pub wikilinks: Vec<Wikilink>,
}

/// Regex patterns for different wikilink formats
static WIKILINK_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        // [[Note Name|Display Text]] - with display text
        Regex::new(r"\[\[([^\|\]]+)\|([^\]]+)\]\]").unwrap(),
        // [[folder/Note Name]] or [[Note Name]] - without display text
        Regex::new(r"\[\[([^\|\]]+)\]\]").unwrap(),
    ]
});

/// Wikilink parser for processing Obsidian-style wikilinks
pub struct WikilinkParser {
    /// Vault root path for resolving file paths
    vault_root: PathBuf,
    /// Vault name for generating obsidian:// URLs
    vault_name: String,
}

impl WikilinkParser {
    /// Create a new wikilink parser
    pub fn new(vault_root: PathBuf, vault_name: String) -> Self {
        Self {
            vault_root,
            vault_name,
        }
    }

    /// Parse wikilinks from content and return summary
    pub fn parse_wikilinks(&self, content: &str) -> WikilinkSummary {
        let mut wikilinks = Vec::new();
        let mut processed_ranges = Vec::new(); // To avoid duplicate matches

        // Process each regex pattern in order of specificity
        for pattern in WIKILINK_PATTERNS.iter() {
            for mat in pattern.find_iter(content) {
                let start_pos = mat.start();
                let end_pos = mat.end();
                
                // Check if this range overlaps with already processed ranges
                if processed_ranges.iter().any(|(s, e): &(usize, usize)| {
                    start_pos < *e && end_pos > *s
                }) {
                    continue; // Skip overlapping matches
                }

                let full_match = mat.as_str();
                let caps = pattern.captures(full_match).unwrap();
                
                let (target_file, display_text) = if caps.len() == 3 {
                    // Pattern with display text: [[target|display]]
                    (caps.get(1).unwrap().as_str(), Some(caps.get(2).unwrap().as_str()))
                } else {
                    // Pattern without display text: [[target]]
                    (caps.get(1).unwrap().as_str(), None)
                };

                let wikilink = self.create_wikilink(
                    full_match.to_string(),
                    target_file,
                    display_text,
                    start_pos,
                    end_pos,
                );

                wikilinks.push(wikilink);
                processed_ranges.push((start_pos, end_pos));
            }
        }

        // Sort wikilinks by position in text
        wikilinks.sort_by(|a, b| a.start_pos.cmp(&b.start_pos));

        // Calculate summary statistics
        let total_count = wikilinks.len();
        let valid_count = wikilinks.iter().filter(|w| w.is_valid).count();
        let broken_count = total_count - valid_count;

        WikilinkSummary {
            total_count,
            valid_count,
            broken_count,
            wikilinks,
        }
    }

    /// Create a wikilink object with validation and URL generation
    fn create_wikilink(
        &self,
        raw_text: String,
        target_file: &str,
        display_text: Option<&str>,
        start_pos: usize,
        end_pos: usize,
    ) -> Wikilink {
        let target_file = target_file.trim();
        let display_text = display_text.map(|s| s.trim().to_string());

        // Try to resolve the target file path
        let (is_valid, resolved_path, obsidian_url) = self.resolve_target_file(target_file);

        Wikilink {
            raw_text,
            target_file: target_file.to_string(),
            display_text,
            obsidian_url,
            is_valid,
            resolved_path,
            start_pos,
            end_pos,
        }
    }

    /// Resolve target file and generate obsidian:// URL
    fn resolve_target_file(&self, target: &str) -> (bool, Option<String>, String) {
        // Clean up the target: remove leading/trailing whitespace
        let target = target.trim();
        
        // Try different resolution strategies
        let possible_paths = self.generate_possible_paths(target);
        
        for path in possible_paths {
            let full_path = self.vault_root.join(&path);
            if full_path.exists() && full_path.is_file() {
                // File exists - generate obsidian:// URL
                let encoded_path = encode(&path);
                let url = format!(
                    "obsidian://open?vault={}&file={}",
                    encode(&self.vault_name),
                    encoded_path
                );
                
                return (true, Some(path), url);
            }
        }

        // File not found - still generate URL for the most likely path
        let likely_path = if target.ends_with(".md") {
            target.to_string()
        } else {
            format!("{}.md", target)
        };
        
        let encoded_path = encode(&likely_path);
        let url = format!(
            "obsidian://open?vault={}&file={}",
            encode(&self.vault_name),
            encoded_path
        );

        (false, None, url)
    }

    /// Generate possible file paths for a target
    fn generate_possible_paths(&self, target: &str) -> Vec<String> {
        let mut paths = Vec::new();

        // If target already has .md extension, use as-is
        if target.ends_with(".md") {
            paths.push(target.to_string());
        } else {
            // Add .md extension
            paths.push(format!("{}.md", target));
        }

        // If target contains path separators, try as a direct path
        if target.contains('/') || target.contains('\\') {
            if !target.ends_with(".md") {
                paths.push(format!("{}.md", target));
            }
            paths.push(target.to_string());
        } else {
            // For simple names, also try looking in common subdirectories
            let common_folders = ["Daily Notes", "Templates", "Archive", "Attachments"];
            for folder in common_folders {
                if target.ends_with(".md") {
                    paths.push(format!("{}/{}", folder, target));
                } else {
                    paths.push(format!("{}/{}.md", folder, target));
                }
            }
        }

        paths
    }

    /// Check if content contains any wikilinks (for performance optimization)
    pub fn has_wikilinks(content: &str) -> bool {
        content.contains("[[") && content.contains("]]")
    }

    /// Extract just the wikilink targets from content (lightweight operation)
    pub fn extract_targets(&self, content: &str) -> Vec<String> {
        if !Self::has_wikilinks(content) {
            return Vec::new();
        }

        let mut targets = Vec::new();
        for pattern in WIKILINK_PATTERNS.iter() {
            for caps in pattern.captures_iter(content) {
                let target = if caps.len() == 3 {
                    caps.get(1).unwrap().as_str()
                } else {
                    caps.get(1).unwrap().as_str()
                };
                targets.push(target.trim().to_string());
            }
        }

        targets
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn create_test_parser() -> (WikilinkParser, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let vault_root = temp_dir.path().to_path_buf();
        let parser = WikilinkParser::new(vault_root, "TestVault".to_string());
        (parser, temp_dir)
    }

    #[test]
    fn test_basic_wikilink_parsing() {
        let (parser, _temp) = create_test_parser();
        let content = "This is a [[Basic Note]] link.";
        
        let summary = parser.parse_wikilinks(content);
        assert_eq!(summary.total_count, 1);
        assert_eq!(summary.wikilinks[0].target_file, "Basic Note");
        assert_eq!(summary.wikilinks[0].display_text, None);
        assert!(summary.wikilinks[0].obsidian_url.contains("obsidian://"));
    }

    #[test]
    fn test_wikilink_with_display_text() {
        let (parser, _temp) = create_test_parser();
        let content = "Check out [[Important Document|this document]].";
        
        let summary = parser.parse_wikilinks(content);
        assert_eq!(summary.total_count, 1);
        assert_eq!(summary.wikilinks[0].target_file, "Important Document");
        assert_eq!(summary.wikilinks[0].display_text, Some("this document".to_string()));
    }

    #[test]
    fn test_multiple_wikilinks() {
        let (parser, _temp) = create_test_parser();
        let content = "See [[Note 1]] and [[Note 2|second note]] for details.";
        
        let summary = parser.parse_wikilinks(content);
        assert_eq!(summary.total_count, 2);
        assert_eq!(summary.wikilinks[0].target_file, "Note 1");
        assert_eq!(summary.wikilinks[1].target_file, "Note 2");
    }

    #[test]
    fn test_wikilink_validation() {
        let (parser, temp) = create_test_parser();
        
        // Create a test file
        let test_file = temp.path().join("Existing Note.md");
        fs::write(&test_file, "# Existing Note\nContent here.").unwrap();
        
        let content = "Links: [[Existing Note]] and [[Missing Note]]";
        let summary = parser.parse_wikilinks(content);
        
        assert_eq!(summary.total_count, 2);
        assert_eq!(summary.valid_count, 1);
        assert_eq!(summary.broken_count, 1);
        
        // First link should be valid
        assert!(summary.wikilinks[0].is_valid);
        assert!(summary.wikilinks[0].resolved_path.is_some());
        
        // Second link should be invalid
        assert!(!summary.wikilinks[1].is_valid);
        assert!(summary.wikilinks[1].resolved_path.is_none());
    }

    #[test]
    fn test_folder_paths() {
        let (parser, temp) = create_test_parser();
        
        // Create folder structure
        let folder = temp.path().join("Subfolder");
        fs::create_dir(&folder).unwrap();
        let test_file = folder.join("Nested Note.md");
        fs::write(&test_file, "# Nested Note").unwrap();
        
        let content = "See [[Subfolder/Nested Note]] for more info.";
        let summary = parser.parse_wikilinks(content);
        
        assert_eq!(summary.total_count, 1);
        assert_eq!(summary.valid_count, 1);
        assert!(summary.wikilinks[0].is_valid);
    }

    #[test]
    fn test_has_wikilinks() {
        assert!(WikilinkParser::has_wikilinks("Text with [[link]]"));
        assert!(!WikilinkParser::has_wikilinks("Text without links"));
        assert!(!WikilinkParser::has_wikilinks("Text with [single brackets]"));
    }
}