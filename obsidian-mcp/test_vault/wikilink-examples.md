# Wikilink Test Examples

This note contains various types of wikilinks to test the parsing functionality.

## Basic Wikilinks
- Simple link: [[Welcome]]
- Link to existing file: [[plain-note]]
- Link to non-existent file: [[Missing Note]]

## Wikilinks with Display Text
- Basic with display: [[Welcome|Welcome Page]]
- Custom display: [[plain-note|My Plain Note]]
- Missing with display: [[Nonexistent|This Won't Work]]

## Folder Structure Links
- Subfolder link: [[test_metadata/sample]]
- Deep folder: [[Projects/ObsidianMCP]]
- Missing folder: [[Archive/Old Notes]]

## Mixed Content
Some text here with [[Welcome]] inline and then more text.
Multiple links in one sentence: [[plain-note]] and [[Welcome|the welcome page]].

Check out [[existing-with-frontmatter]] for metadata examples.

## Edge Cases
- Empty display: [[Welcome|]]
- Nested brackets: This [[has some [[weird]] stuff]] but only outer should parse
- Special characters: [[Notes with Symbols & More]]