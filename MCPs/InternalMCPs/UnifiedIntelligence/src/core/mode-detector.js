export class ModeDetector {
  constructor() {
    // The order of these rules matters. More specific rules should come first.
    this.rules = [
      { 
        mode: 'debug', 
        keywords: ['error', 'fix', 'bug', 'issue', 'problem', 'debug', 'troubleshoot', 'crash', 'fail', 'broken', 'not working'],
        patterns: [/\berror\s*(code|message)?/i, /exception|stacktrace/i, /doesn't work/i]
      },
      { 
        mode: 'test',
        keywords: ['test', 'testing', 'verify', 'validate', 'check', 'ensure', 'assert', 'expect', 'should'],
        patterns: [/unit test|integration test/i, /test case|test suite/i, /passes?\s+test/i]
      },
      { 
        mode: 'design', 
        keywords: ['design', 'architecture', 'plan', 'structure', 'component', 'interface', 'schema', 'pattern', 'approach'],
        patterns: [/how\s+(should|would|could)\s+we/i, /design\s+pattern/i, /architect(ure)?/i]
      },
      { 
        mode: 'decision',
        keywords: ['decide', 'choice', 'option', 'alternative', 'versus', 'vs', 'compare', 'choose', 'better', 'pros', 'cons', 'trade-off'],
        patterns: [/should\s+(i|we)\s+use/i, /which\s+(one|approach|method)/i, /pros?\s+(and|&)\s+cons?/i]
      },
      { 
        mode: 'learn', 
        keywords: ['learn', 'research', 'understand', 'what is', 'how does', 'explain', 'why', 'concept', 'theory'],
        patterns: [/what\s+(is|are|does)/i, /how\s+(does|do|to)/i, /explain\s+(how|what|why)/i]
      },
      { 
        mode: 'task', 
        keywords: ['implement', 'build', 'create', 'add', 'update', 'modify', 'let me', 'i will', 'i need to', 'to do', 'next step', 'task'],
        patterns: [/need\s+to\s+(implement|build|create)/i, /let's\s+(add|create|build)/i, /working\s+on/i]
      },
      { 
        mode: 'convo', 
        keywords: ['think', 'believe', 'opinion', 'feel', 'wonder', 'curious', 'interesting'],
        patterns: [/i\s+(think|believe|feel)/i, /in\s+my\s+opinion/i, /interesting\s+that/i]
      },
    ];
    
    // Mode confidence thresholds
    this.confidenceBoost = {
      debug: 0.1,    // Boost confidence when debugging
      test: 0.1,     // Testing requires precision
      design: 0.05,  // Design thinking benefits from confidence
      decision: 0.15, // Decision making needs high confidence
      learn: 0,      // Learning is exploratory
      task: 0.05,    // Task execution benefits from confidence
      convo: 0       // Conversation is neutral
    };
  }

  /**
   * Detects the thinking mode from the content of a thought.
   * @param {string} thoughtContent - The content of the thought.
   * @returns {object} - The detected mode and confidence adjustment.
   */
  detect(thoughtContent) {
    const lowerCaseContent = thoughtContent.toLowerCase();
    const scores = {};

    // Score each mode based on keyword and pattern matches
    for (const rule of this.rules) {
      let score = 0;
      
      // Check keywords
      for (const keyword of rule.keywords) {
        const regex = new RegExp(`\\b${keyword}\\b`, 'i');
        if (regex.test(lowerCaseContent)) {
          score += 1;
        }
      }
      
      // Check patterns (weighted more heavily)
      if (rule.patterns) {
        for (const pattern of rule.patterns) {
          if (pattern.test(thoughtContent)) {
            score += 2;
          }
        }
      }
      
      if (score > 0) {
        scores[rule.mode] = score;
      }
    }

    // Find the mode with highest score with deterministic tie-breaking
    let detectedMode = 'convo';
    let highestScore = 0;
    
    // Sort entries by mode name for deterministic tie-breaking
    const sortedScores = Object.entries(scores).sort(([a], [b]) => a.localeCompare(b));
    
    for (const [mode, score] of sortedScores) {
      if (score > highestScore) {
        highestScore = score;
        detectedMode = mode;
      }
    }
    
    // Apply minimum confidence threshold (at least 1 point to override default 'convo')
    if (highestScore === 0) {
      detectedMode = 'convo';
    }

    return {
      mode: detectedMode,
      confidenceBoost: this.confidenceBoost[detectedMode] || 0,
      scores: scores // For debugging/transparency
    };
  }

  /**
   * Get simple mode string for backward compatibility
   * @param {string} thoughtContent - The content of the thought.
   * @returns {string} - The detected mode string.
   */
  detectMode(thoughtContent) {
    return this.detect(thoughtContent).mode;
  }
}
