use crate::config::VaultConfig;
use crate::error::{ObsidianMcpError, ObsidianResult};
use crate::models::*;
use chrono::{DateTime, Utc};
use std::fs;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// Vault operations manager
pub struct VaultManager {
    config: VaultConfig,
    root_path: PathBuf,
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
        
        tracing::info!("VaultManager initialized with path: {}", root_path.display());
        Ok(Self { config, root_path })
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
        
        let content = if include_content && !is_directory && self.is_allowed_extension(&abs_path) {
            // Check file size
            if metadata.len() > self.config.max_file_size {
                return Err(ObsidianMcpError::InvalidFileOperation {
                    operation: "read".to_string(),
                    path: format!("File too large: {} bytes", metadata.len()),
                });
            }
            
            Some(fs::read_to_string(&abs_path)?)
        } else {
            None
        };

        Ok(VaultFile {
            path: relative_path.to_string(),
            content,
            metadata: self.create_file_metadata(&metadata, &abs_path),
            is_directory,
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

        // Write the file
        fs::write(&abs_path, &params.content)?;
        
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

        // Write the file
        fs::write(&abs_path, &params.content)?;
        
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

            // Search in filename
            if rel_path.to_lowercase().contains(&params.query.to_lowercase()) {
                is_match = true;
            }

            // Search in content if requested and it's a text file
            if !is_match && self.is_allowed_extension(path) {
                if let Ok(content) = fs::read_to_string(path) {
                    if content.to_lowercase().contains(&params.query.to_lowercase()) {
                        is_match = true;
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

        Ok(crate::models::SearchResults {
            files: matching_files,
            total_matches,
            query: params.query.clone(),
        })
    }
}