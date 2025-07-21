use crate::config::VaultConfig;
use crate::error::{ObsidianMcpError, ObsidianResult};
use crate::models::*;
use crate::wikilink::{WikilinkParser, WikilinkSummary};
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// Vault operations manager
pub struct VaultManager {
    config: VaultConfig,
    root_path: PathBuf,
    wikilink_parser: Option<WikilinkParser>,
}

impl VaultManager {
    pub fn new(config: VaultConfig) -> ObsidianResult<Self> {
        let root_path = config.root_path.clone();
        
        // Validate vault directory exists and is accessible
        if !root_path.exists() {
            return Err(ObsidianMcpError::InvalidVaultPath {
                path: format!("Vault directory does not exist: {}", root_path.display()),
            });
        }
        
        if !root_path.is_dir() {
            return Err(ObsidianMcpError::InvalidVaultPath {
                path: format!("Vault path is not a directory: {}", root_path.display()),
            });
        }
        
        // Test read access
        if let Err(e) = fs::read_dir(&root_path) {
            return Err(ObsidianMcpError::InvalidVaultPath {
                path: format!("Cannot read vault directory {}: {}", root_path.display(), e),
            });
        }
        
        // Initialize wikilink parser if enabled
        let wikilink_parser = if config.enable_wikilinks {
            Some(WikilinkParser::new(root_path.clone(), config.vault_name.clone()))
        } else {
            None
        };

        tracing::info!("VaultManager initialized with path: {}", root_path.display());
        Ok(Self { 
            config, 
            root_path,
            wikilink_parser,
        })
    }

    /// Get vault information
    pub fn get_vault_info(&self) -> ObsidianResult<VaultInfo> {
        let mut file_count = 0;
        let mut total_size = 0;

        for entry in WalkDir::new(&self.root_path) {
            let entry = entry?;
            if entry.file_type().is_file() {
                file_count += 1;
                if let Ok(metadata) = entry.metadata() {
                    total_size += metadata.len();
                }
            }
        }

        Ok(VaultInfo {
            root_path: self.root_path.display().to_string(),
            file_count,
            total_size,
            is_valid: true,
        })
    }

    /// Convert absolute path to relative path from vault root
    fn to_relative_path(&self, path: &Path) -> ObsidianResult<String> {
        let rel_path = path.strip_prefix(&self.root_path)
            .map_err(|_| ObsidianMcpError::InvalidFileOperation {
                operation: "relative_path".to_string(),
                path: path.display().to_string(),
            })?;
        
        Ok(rel_path.display().to_string())
    }

    /// Convert relative path to absolute path within vault
    fn to_absolute_path(&self, relative_path: &str) -> ObsidianResult<PathBuf> {
        let path = self.root_path.join(relative_path);
        
        // Ensure the resolved path is still within the vault
        let canonical_vault = self.root_path.canonicalize()?;
        let canonical_path = path.parent()
            .unwrap_or(&path)
            .canonicalize()
            .unwrap_or_else(|_| path.clone());
            
        if !canonical_path.starts_with(&canonical_vault) {
            return Err(ObsidianMcpError::VaultAccessDenied {
                reason: "Path outside vault boundaries".to_string(),
            });
        }
        
        Ok(path)
    }    /// Check if file extension is allowed
    fn is_allowed_extension(&self, path: &Path) -> bool {
        if let Some(ext) = path.extension() {
            if let Some(ext_str) = ext.to_str() {
                return self.config.allowed_extensions.contains(&ext_str.to_lowercase());
            }
        }
        false
    }

    /// Parse frontmatter and content from a file
    /// Returns (frontmatter, tags, content)
    fn parse_frontmatter(&self, content: &str) -> (Option<HashMap<String, serde_json::Value>>, Vec<String>, String) {
        let content = content.trim_start();
        
        // Check if content starts with YAML frontmatter delimiter
        if !content.starts_with("---\n") && !content.starts_with("---\r\n") {
            // No frontmatter, extract inline tags from content
            let tags = self.extract_inline_tags(content);
            return (None, tags, content.to_string());
        }

        // Find the end of frontmatter
        let lines: Vec<&str> = content.lines().collect();
        let mut frontmatter_end = None;
        
        for (i, line) in lines.iter().enumerate().skip(1) {
            if line.trim() == "---" {
                frontmatter_end = Some(i);
                break;
            }
        }

        let Some(end_line) = frontmatter_end else {
            // Malformed frontmatter, treat as regular content
            let tags = self.extract_inline_tags(content);
            return (None, tags, content.to_string());
        };

        // Extract frontmatter content
        let frontmatter_content = lines[1..end_line].join("\n");
        let remaining_content = if end_line + 1 < lines.len() {
            lines[end_line + 1..].join("\n")
        } else {
            String::new()
        };

        // Parse YAML frontmatter
        let frontmatter = match serde_yaml::from_str::<HashMap<String, serde_json::Value>>(&frontmatter_content) {
            Ok(fm) => Some(fm),
            Err(_) => {
                // Failed to parse YAML, treat as regular content
                let tags = self.extract_inline_tags(content);
                return (None, tags, content.to_string());
            }
        };

        // Extract tags from frontmatter and content
        let mut tags = Vec::new();
        
        // Tags from frontmatter
        if let Some(fm) = &frontmatter {
            if let Some(fm_tags) = fm.get("tags") {
                match fm_tags {
                    serde_json::Value::Array(tag_array) => {
                        for tag in tag_array {
                            if let serde_json::Value::String(tag_str) = tag {
                                tags.push(tag_str.clone());
                            }
                        }
                    }
                    serde_json::Value::String(tag_str) => {
                        tags.push(tag_str.clone());
                    }
                    _ => {}
                }
            }
        }
        
        // Tags from content
        let inline_tags = self.extract_inline_tags(&remaining_content);
        tags.extend(inline_tags);

        (frontmatter, tags, remaining_content)
    }

    /// Extract inline tags (#tag format) from content
    fn extract_inline_tags(&self, content: &str) -> Vec<String> {
        let mut tags = Vec::new();
        
        // Simple regex-like extraction for #tag patterns
        let words: Vec<&str> = content.split_whitespace().collect();
        for word in words {
            if word.starts_with('#') && word.len() > 1 {
                let tag = word[1..].trim_end_matches(|c: char| !c.is_alphanumeric() && c != '_' && c != '-');
                if !tag.is_empty() {
                    tags.push(tag.to_string());
                }
            }
        }
        
        tags
    }

    /// Generate frontmatter YAML and combine with content
    fn generate_content_with_frontmatter(
        &self,
        content: &str,
        frontmatter: Option<&HashMap<String, serde_json::Value>>,
        tags: Option<&[String]>
    ) -> ObsidianResult<String> {
        // If no frontmatter or tags, return content as-is
        if frontmatter.is_none() && tags.as_ref().map(|t| t.is_empty()).unwrap_or(true) {
            return Ok(content.to_string());
        }

        let mut combined_frontmatter = frontmatter.cloned().unwrap_or_default();
        
        // Add tags to frontmatter if provided
        if let Some(tags) = tags {
            if !tags.is_empty() {
                combined_frontmatter.insert(
                    "tags".to_string(),
                    serde_json::Value::Array(
                        tags.iter().map(|t| serde_json::Value::String(t.clone())).collect()
                    )
                );
            }
        }

        if combined_frontmatter.is_empty() {
            return Ok(content.to_string());
        }

        // Generate YAML frontmatter
        let yaml = serde_yaml::to_string(&combined_frontmatter)
            .map_err(|e| ObsidianMcpError::InvalidFileOperation {
                operation: "generate_frontmatter".to_string(),
                path: format!("Failed to serialize frontmatter to YAML: {}", e),
            })?;

        // Combine frontmatter with content
        let result = format!("---\n{}---\n{}", yaml, content);
        Ok(result)
    }

    /// Merge existing frontmatter with new frontmatter and tags
    /// If new_frontmatter or new_tags is None, preserve existing values
    fn merge_metadata(
        &self,
        existing_frontmatter: Option<HashMap<String, serde_json::Value>>,
        existing_tags: Vec<String>,
        new_frontmatter: Option<&HashMap<String, serde_json::Value>>,
        new_tags: Option<&[String]>
    ) -> (Option<HashMap<String, serde_json::Value>>, Option<Vec<String>>) {
        // Handle frontmatter
        let merged_frontmatter = match (existing_frontmatter, new_frontmatter) {
            (Some(mut existing), Some(new)) => {
                // Merge new frontmatter into existing
                for (key, value) in new {
                    existing.insert(key.clone(), value.clone());
                }
                Some(existing)
            }
            (existing, None) => existing,
            (None, Some(new)) => Some(new.clone()),
        };

        // Handle tags
        let merged_tags = match new_tags {
            Some(new_tags) => Some(new_tags.to_vec()),
            None => if existing_tags.is_empty() { None } else { Some(existing_tags) },
        };

        (merged_frontmatter, merged_tags)
    }

    /// Parse wikilinks from content if wikilink parsing is enabled
    fn parse_wikilinks_if_enabled(&self, content: &str) -> Option<WikilinkSummary> {
        if let Some(ref parser) = self.wikilink_parser {
            if WikilinkParser::has_wikilinks(content) {
                Some(parser.parse_wikilinks(content))
            } else {
                Some(WikilinkSummary {
                    total_count: 0,
                    valid_count: 0,
                    broken_count: 0,
                    wikilinks: Vec::new(),
                })
            }
        } else {
            None
        }
    }

    /// Create file metadata from filesystem metadata
    fn create_file_metadata(&self, metadata: &fs::Metadata, path: &Path) -> FileMetadata {
        let created = metadata.created()
            .ok()
            .and_then(|t| DateTime::from_timestamp(
                t.duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs() as i64, 0
            ))
            .unwrap_or_else(|| Utc::now());
            
        let modified = metadata.modified()
            .ok()
            .and_then(|t| DateTime::from_timestamp(
                t.duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_secs() as i64, 0
            ))
            .unwrap_or_else(|| Utc::now());

        FileMetadata {
            size: metadata.len(),
            created,
            modified,
            extension: path.extension().and_then(|s| s.to_str()).map(|s| s.to_lowercase()),
        }
    }

    /// Read a file and return VaultFile
    pub fn read_file(&self, relative_path: &str, include_content: bool) -> ObsidianResult<VaultFile> {
        let abs_path = self.to_absolute_path(relative_path)?;
        
        if !abs_path.exists() {
            return Err(ObsidianMcpError::FileNotFound {
                path: relative_path.to_string(),
            });
        }

        let metadata = fs::metadata(&abs_path)?;
        let is_directory = metadata.is_dir();
        
        let (content, wikilinks) = if include_content && !is_directory && self.is_allowed_extension(&abs_path) {
            // Check file size
            if metadata.len() > self.config.max_file_size {
                return Err(ObsidianMcpError::InvalidFileOperation {
                    operation: "read".to_string(),
                    path: format!("File too large: {} bytes", metadata.len()),
                });
            }
            
            let file_content = fs::read_to_string(&abs_path)?;
            let wikilinks = self.parse_wikilinks_if_enabled(&file_content);
            (Some(file_content), wikilinks)
        } else {
            (None, None)
        };

        Ok(VaultFile {
            path: relative_path.to_string(),
            content,
            metadata: self.create_file_metadata(&metadata, &abs_path),
            is_directory,
            wikilinks,
        })
    }

    /// Create a new file
    pub fn create_file(&self, params: &crate::models::CreateFileParams) -> ObsidianResult<VaultFile> {
        let abs_path = self.to_absolute_path(&params.path)?;
        
        // Check if file already exists
        if abs_path.exists() && !params.overwrite {
            return Err(ObsidianMcpError::InvalidFileOperation {
                operation: "create".to_string(),
                path: format!("File already exists: {}", params.path),
            });
        }

        // Check file extension
        if !self.is_allowed_extension(&abs_path) {
            return Err(ObsidianMcpError::InvalidFileOperation {
                operation: "create".to_string(),
                path: format!("File extension not allowed: {}", params.path),
            });
        }

        // Create parent directories if needed (only if they don't exist and create_dirs is true)
        if params.create_dirs {
            if let Some(parent) = abs_path.parent() {
                if !parent.exists() {
                    fs::create_dir_all(parent).map_err(|e| ObsidianMcpError::InvalidFileOperation {
                        operation: "create".to_string(),
                        path: format!("Cannot create parent directory {}: {}. This may be due to insufficient permissions or a read-only filesystem.", parent.display(), e),
                    })?;
                }
            }
        } else if let Some(parent) = abs_path.parent() {
            // Ensure parent directory exists when create_dirs is false
            if !parent.exists() {
                return Err(ObsidianMcpError::InvalidFileOperation {
                    operation: "create".to_string(),
                    path: format!("Parent directory does not exist: {}. Set create_dirs=true to create it.", parent.display()),
                });
            }
        }

        // Generate content with frontmatter and tags
        let final_content = self.generate_content_with_frontmatter(
            &params.content,
            params.frontmatter.as_ref(),
            params.tags.as_deref()
        )?;

        // Write the file
        fs::write(&abs_path, &final_content)?;
        
        // Return the created file info
        self.read_file(&params.path, false)
    }

    /// Update an existing file
    pub fn update_file(&self, params: &crate::models::UpdateFileParams) -> ObsidianResult<VaultFile> {
        let abs_path = self.to_absolute_path(&params.path)?;
        
        // Check if file exists or if we should create it
        if !abs_path.exists() && !params.create_if_missing {
            return Err(ObsidianMcpError::FileNotFound {
                path: params.path.clone(),
            });
        }

        // Check file extension
        if !self.is_allowed_extension(&abs_path) {
            return Err(ObsidianMcpError::InvalidFileOperation {
                operation: "update".to_string(),
                path: format!("File extension not allowed: {}", params.path),
            });
        }

        // Ensure parent directories exist if file doesn't exist
        if !abs_path.exists() {
            if let Some(parent) = abs_path.parent() {
                if !parent.exists() {
                    fs::create_dir_all(parent).map_err(|e| ObsidianMcpError::InvalidFileOperation {
                        operation: "update".to_string(),
                        path: format!("Cannot create parent directory {}: {}. This may be due to insufficient permissions or a read-only filesystem.", parent.display(), e),
                    })?;
                }
            }
        }

        // If file exists, parse existing metadata to preserve it if not overridden
        let (existing_frontmatter, existing_tags) = if abs_path.exists() {
            let existing_content = fs::read_to_string(&abs_path)?;
            let (fm, tags, _) = self.parse_frontmatter(&existing_content);
            (fm, tags)
        } else {
            (None, Vec::new())
        };

        // Merge existing metadata with new metadata
        let (merged_frontmatter, merged_tags) = self.merge_metadata(
            existing_frontmatter,
            existing_tags,
            params.frontmatter.as_ref(),
            params.tags.as_deref()
        );

        // Generate content with merged frontmatter and tags
        let final_content = self.generate_content_with_frontmatter(
            &params.content,
            merged_frontmatter.as_ref(),
            merged_tags.as_deref()
        )?;

        // Write the file
        fs::write(&abs_path, &final_content)?;
        
        // Return the updated file info
        self.read_file(&params.path, false)
    }

    /// Delete a file or directory
    pub fn delete_file(&self, params: &crate::models::DeleteFileParams) -> ObsidianResult<()> {
        let abs_path = self.to_absolute_path(&params.path)?;
        
        if !abs_path.exists() {
            return Err(ObsidianMcpError::FileNotFound {
                path: params.path.clone(),
            });
        }

        if abs_path.is_dir() {
            if params.recursive {
                fs::remove_dir_all(&abs_path)?;
            } else {
                fs::remove_dir(&abs_path)?;
            }
        } else {
            fs::remove_file(&abs_path)?;
        }

        Ok(())
    }

    /// Move/rename a file
    pub fn move_file(&self, params: &crate::models::MoveFileParams) -> ObsidianResult<VaultFile> {
        let from_abs = self.to_absolute_path(&params.from_path)?;
        let to_abs = self.to_absolute_path(&params.to_path)?;
        
        // Check source exists
        if !from_abs.exists() {
            return Err(ObsidianMcpError::FileNotFound {
                path: params.from_path.clone(),
            });
        }

        // Check if destination exists
        if to_abs.exists() && !params.overwrite {
            return Err(ObsidianMcpError::InvalidFileOperation {
                operation: "move".to_string(),
                path: format!("Destination already exists: {}", params.to_path),
            });
        }

        // Check destination extension
        if !from_abs.is_dir() && !self.is_allowed_extension(&to_abs) {
            return Err(ObsidianMcpError::InvalidFileOperation {
                operation: "move".to_string(),
                path: format!("Destination extension not allowed: {}", params.to_path),
            });
        }

        // Ensure parent directories exist for destination
        if let Some(parent) = to_abs.parent() {
            if !parent.exists() {
                fs::create_dir_all(parent).map_err(|e| ObsidianMcpError::InvalidFileOperation {
                    operation: "move".to_string(),
                    path: format!("Cannot create destination directory {}: {}. This may be due to insufficient permissions or a read-only filesystem.", parent.display(), e),
                })?;
            }
        }

        // Perform the move
        fs::rename(&from_abs, &to_abs)?;
        
        // Return the moved file info
        self.read_file(&params.to_path, false)
    }

    /// List directory contents
    pub fn list_directory(&self, relative_path: Option<&str>) -> ObsidianResult<Vec<VaultFile>> {
        let dir_path = match relative_path {
            Some(path) => self.to_absolute_path(path)?,
            None => self.root_path.clone(),
        };

        if !dir_path.exists() {
            return Err(ObsidianMcpError::FileNotFound {
                path: relative_path.unwrap_or(".").to_string(),
            });
        }

        if !dir_path.is_dir() {
            return Err(ObsidianMcpError::InvalidFileOperation {
                operation: "list".to_string(),
                path: "Path is not a directory".to_string(),
            });
        }

        let mut files = Vec::new();
        for entry in fs::read_dir(&dir_path)? {
            let entry = entry?;
            let path = entry.path();
            
            // Convert back to relative path
            let rel_path = self.to_relative_path(&path)?;
            
            // Skip hidden files unless configured otherwise
            if path.file_name()
                .and_then(|n| n.to_str())
                .map(|n| n.starts_with('.'))
                .unwrap_or(false) 
            {
                continue;
            }

            // Create VaultFile entry
            let metadata = entry.metadata()?;
            files.push(VaultFile {
                path: rel_path,
                content: None,
                metadata: self.create_file_metadata(&metadata, &path),
                is_directory: metadata.is_dir(),
                wikilinks: None, // Directory listings don't include content, so no wikilinks
            });
        }

        // Sort by name
        files.sort_by(|a, b| a.path.cmp(&b.path));
        Ok(files)
    }

    /// Search for files by name or content
    pub fn search_files(&self, params: &crate::models::SearchParams) -> ObsidianResult<crate::models::SearchResults> {
        let search_root = match &params.path_prefix {
            Some(prefix) => self.to_absolute_path(prefix)?,
            None => self.root_path.clone(),
        };

        let mut matching_files = Vec::new();
        let mut total_matches = 0;

        for entry in WalkDir::new(search_root) {
            let entry = entry.map_err(|e| ObsidianMcpError::InvalidFileOperation {
                operation: "search".to_string(),
                path: format!("Walk directory error: {}", e),
            })?;

            let path = entry.path();
            
            // Skip directories unless we're looking for directory names
            if path.is_dir() {
                continue;
            }

            // Skip hidden files
            if path.file_name()
                .and_then(|n| n.to_str())
                .map(|n| n.starts_with('.'))
                .unwrap_or(false) 
            {
                continue;
            }

            // Check file extension filter
            if let Some(ref extensions) = params.extensions {
                let ext = path.extension()
                    .and_then(|e| e.to_str())
                    .map(|e| e.to_lowercase());
                
                if !ext.map(|e| extensions.contains(&e)).unwrap_or(false) {
                    continue;
                }
            } else if !self.is_allowed_extension(path) {
                continue;
            }

            let rel_path = self.to_relative_path(path)?;
            let mut is_match = false;
            let mut search_content = None;

            // Search in filename
            if rel_path.to_lowercase().contains(&params.query.to_lowercase()) {
                is_match = true;
            }

            // Search in content if not already matched and it's a text file
            if !is_match && self.is_allowed_extension(path) {
                if let Ok(content) = fs::read_to_string(path) {
                    search_content = Some(content.clone());
                    if content.to_lowercase().contains(&params.query.to_lowercase()) {
                        is_match = true;
                    }
                }
            }

            // Also search in wikilink targets if wikilink parsing is enabled
            if !is_match && self.wikilink_parser.is_some() {
                if let Some(ref content) = search_content.or_else(|| {
                    if self.is_allowed_extension(path) {
                        fs::read_to_string(path).ok()
                    } else {
                        None
                    }
                }) {
                    if let Some(ref parser) = self.wikilink_parser {
                        let targets = parser.extract_targets(content);
                        if targets.iter().any(|target| 
                            target.to_lowercase().contains(&params.query.to_lowercase())
                        ) {
                            is_match = true;
                        }
                    }
                }
            }

            if is_match {
                total_matches += 1;
                
                if matching_files.len() < params.limit {
                    match self.read_file(&rel_path, params.include_content) {
                        Ok(vault_file) => matching_files.push(vault_file),
                        Err(_) => continue, // Skip files that can't be read
                    }
                }
            }
        }

        // Generate wikilink summary if wikilinks are enabled
        let wikilink_summary = if self.config.enable_wikilinks && params.include_content {
            self.generate_wikilink_search_summary(&matching_files)
        } else {
            None
        };

        Ok(crate::models::SearchResults {
            files: matching_files,
            total_matches,
            query: params.query.clone(),
            wikilink_summary,
        })
    }

    /// Generate summary of wikilinks across search results
    fn generate_wikilink_search_summary(&self, files: &[VaultFile]) -> Option<WikilinkSearchSummary> {
        let mut files_with_wikilinks = 0;
        let mut total_wikilinks = 0;
        let mut total_valid_wikilinks = 0;
        let mut total_broken_wikilinks = 0;

        for file in files {
            if let Some(ref wikilink_summary) = file.wikilinks {
                if wikilink_summary.total_count > 0 {
                    files_with_wikilinks += 1;
                }
                total_wikilinks += wikilink_summary.total_count;
                total_valid_wikilinks += wikilink_summary.valid_count;
                total_broken_wikilinks += wikilink_summary.broken_count;
            }
        }

        if total_wikilinks > 0 {
            Some(WikilinkSearchSummary {
                files_with_wikilinks,
                total_wikilinks,
                total_valid_wikilinks,
                total_broken_wikilinks,
            })
        } else {
            None
        }
    }
}