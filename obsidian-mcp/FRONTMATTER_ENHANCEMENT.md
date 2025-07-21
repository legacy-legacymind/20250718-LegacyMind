# Frontmatter and Tags Enhancement

## Overview
Successfully implemented frontmatter and tags support for ObsidianMCP browse operations while maintaining the existing 2-tool architecture.

## New Features

### 1. Enhanced BrowseParams
Added optional parameters to the browse tool:
- `frontmatter`: Optional `HashMap<String, serde_json::Value>` for YAML metadata
- `tags`: Optional `Vec<String>` for file tags

### 2. Create Operations with Metadata
```json
{
  "operation": "create", 
  "path": "note.md",
  "content": "Content...",
  "frontmatter": {"type": "planning-doc", "importance": 8},
  "tags": ["obsidian", "development"]
}
```

### 3. Update Operations with Metadata Preservation
- **Content-only updates**: Preserve existing frontmatter and tags
- **Metadata updates**: Merge new frontmatter with existing, replace tags if provided
```json
{
  "operation": "update",
  "path": "note.md",
  "content": "New content...",
  "frontmatter": {"status": "completed"},
  "tags": ["finished"]
}
```

## Implementation Details

### Dependencies Added
- `serde_yaml = "0.9"` for YAML frontmatter parsing

### Key Functions
1. **`parse_frontmatter()`**: Extracts YAML frontmatter and inline tags from content
2. **`generate_content_with_frontmatter()`**: Combines content with frontmatter header
3. **`merge_metadata()`**: Intelligently merges existing and new metadata
4. **`extract_inline_tags()`**: Finds #tag patterns in content

### Frontmatter Format
Standard YAML frontmatter format:
```yaml
---
type: planning-doc
importance: 8
tags: [obsidian, development]
---
# Note Content
```

### Tag Handling
- Tags from frontmatter (`tags` field)
- Inline tags from content (`#tag` format)
- Update operations can specify new tags or preserve existing ones

## Backward Compatibility
- All existing browse operations work unchanged
- Frontmatter and tags parameters are optional
- Files without frontmatter work normally

## Testing
- Created test files with various frontmatter scenarios
- Verified successful compilation and build
- All functionality preserved while adding new capabilities

## Usage Examples

### Create with frontmatter:
```json
{
  "operation": "create",
  "path": "project-notes.md",
  "content": "# Project Planning\n\nObjectives...",
  "frontmatter": {"type": "planning-doc", "importance": 8},
  "tags": ["project", "planning"]
}
```

### Update preserving metadata:
```json
{
  "operation": "update",
  "path": "existing-note.md",
  "content": "Updated content..."
}
```

### Update with metadata changes:
```json
{
  "operation": "update",
  "path": "task-note.md",
  "content": "Completed tasks...",
  "frontmatter": {"status": "completed"},
  "tags": ["finished"]
}
```

## Files Modified
- `/src/models.rs`: Added frontmatter/tags to BrowseParams, CreateFileParams, UpdateFileParams
- `/src/vault.rs`: Implemented frontmatter parsing, generation, and merging functions
- `/src/service.rs`: Updated operation handlers and help documentation
- `/Cargo.toml`: Added serde_yaml dependency

The enhancement successfully maintains the 2-tool architecture while providing powerful metadata management capabilities for Obsidian vault operations.