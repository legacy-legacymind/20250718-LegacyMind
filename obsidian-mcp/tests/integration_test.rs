use obsidian_mcp::*;
use std::path::PathBuf;

#[tokio::test]
async fn test_wikilink_parsing_integration() {
    // Set up test vault configuration
    let test_vault_path = PathBuf::from("test_vault");
    let vault_config = VaultConfig {
        root_path: test_vault_path,
        vault_name: "TestVault".to_string(),
        allowed_extensions: vec!["md".to_string()],
        max_file_size: 10 * 1024 * 1024,
        enable_watching: false,
        enable_wikilinks: true,
    };

    // Create vault manager
    let vault_manager = VaultManager::new(vault_config).expect("Failed to create vault manager");

    // Search for files containing "wikilink"
    let search_params = SearchParams {
        query: "wikilink".to_string(),
        path_prefix: None,
        include_content: true,
        limit: 10,
        extensions: Some(vec!["md".to_string()]),
    };

    let results = vault_manager.search_files(&search_params).expect("Search failed");

    // Verify we found the wikilink examples file
    assert!(results.total_matches > 0, "Should find files with wikilinks");
    
    let wikilink_file = results.files.iter()
        .find(|f| f.path.contains("wikilink-examples"))
        .expect("Should find the wikilink-examples.md file");

    // Verify wikilinks were parsed
    assert!(wikilink_file.wikilinks.is_some(), "Should have wikilinks parsed");
    
    let wikilink_summary = wikilink_file.wikilinks.as_ref().unwrap();
    assert!(wikilink_summary.total_count > 0, "Should have found wikilinks");
    
    // Check specific wikilinks
    let welcome_link = wikilink_summary.wikilinks.iter()
        .find(|w| w.target_file == "Welcome");
    assert!(welcome_link.is_some(), "Should find Welcome wikilink");
    assert!(welcome_link.unwrap().is_valid, "Welcome link should be valid");
    assert!(welcome_link.unwrap().obsidian_url.contains("obsidian://"), "Should generate obsidian:// URL");

    // Check for broken link
    let missing_link = wikilink_summary.wikilinks.iter()
        .find(|w| w.target_file == "Missing Note");
    assert!(missing_link.is_some(), "Should find Missing Note wikilink");
    assert!(!missing_link.unwrap().is_valid, "Missing Note link should be invalid");

    // Check display text parsing
    let display_link = wikilink_summary.wikilinks.iter()
        .find(|w| w.display_text.is_some());
    assert!(display_link.is_some(), "Should find wikilink with display text");

    println!("✅ Wikilink integration test passed!");
    println!("Found {} wikilinks ({} valid, {} broken)", 
             wikilink_summary.total_count,
             wikilink_summary.valid_count,
             wikilink_summary.broken_count);

    // Print some example wikilinks
    for (i, wikilink) in wikilink_summary.wikilinks.iter().take(5).enumerate() {
        println!("  {}. {} -> {} (valid: {})", 
                 i + 1,
                 wikilink.raw_text,
                 wikilink.obsidian_url,
                 wikilink.is_valid);
    }
}