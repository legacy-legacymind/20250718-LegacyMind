/**
 * ModeAnalyzer - Classifies the operational mode of thoughts
 * 
 * Modes: debug, design, execute, reflect, question, explore
 */
export class ModeAnalyzer {
  constructor() {
    this.modes = {
      debug: {
        keywords: ['error', 'bug', 'fix', 'problem', 'issue', 'broken', 'fail', 'crash', 'exception', 'debug'],
        patterns: [/why.*not.*work/i, /what.*wrong/i, /how.*fix/i, /problem.*with/i]
      },
      design: {
        keywords: ['design', 'architecture', 'structure', 'pattern', 'plan', 'blueprint', 'model', 'framework'],
        patterns: [/how.*should.*design/i, /what.*architecture/i, /structure.*of/i, /pattern.*for/i]
      },
      execute: {
        keywords: ['implement', 'build', 'create', 'make', 'do', 'execute', 'run', 'perform', 'action'],
        patterns: [/let.*do/i, /going.*to/i, /will.*implement/i, /need.*to.*create/i]
      },
      reflect: {
        keywords: ['learned', 'understand', 'realize', 'insight', 'reflection', 'think', 'consider', 'ponder'],
        patterns: [/i.*learned/i, /now.*understand/i, /this.*means/i, /reflection.*on/i]
      },
      question: {
        keywords: ['what', 'why', 'how', 'when', 'where', 'who', 'question', 'wonder', 'curious'],
        patterns: [/what.*if/i, /why.*does/i, /how.*can/i, /i.*wonder/i, /curious.*about/i]
      },
      explore: {
        keywords: ['explore', 'investigate', 'research', 'discover', 'find', 'search', 'experiment', 'try'],
        patterns: [/let.*explore/i, /investigate.*this/i, /research.*about/i, /experiment.*with/i]
      }
    };
  }

  analyze(content) {
    const scores = {};
    const contentLower = content.toLowerCase();
    
    // Initialize scores
    for (const mode in this.modes) {
      scores[mode] = 0;
    }
    
    // Score based on keywords
    for (const [mode, config] of Object.entries(this.modes)) {
      // Keyword matching
      for (const keyword of config.keywords) {
        if (contentLower.includes(keyword)) {
          scores[mode] += 1;
        }
      }
      
      // Pattern matching
      for (const pattern of config.patterns) {
        if (pattern.test(content)) {
          scores[mode] += 2; // Patterns weigh more
        }
      }
    }
    
    // Find the highest scoring mode
    const maxScore = Math.max(...Object.values(scores));
    const detectedMode = Object.keys(scores).find(mode => scores[mode] === maxScore);
    
    // If no strong signal, classify as 'general'
    const confidence = maxScore > 0 ? Math.min(maxScore / 5, 1) : 0;
    
    return {
      mode: maxScore > 0 ? detectedMode : 'general',
      confidence,
      scores,
      reasoning: this.generateReasoning(detectedMode, maxScore, content)
    };
  }
  
  generateReasoning(mode, score, content) {
    if (score === 0) {
      return 'No clear mode indicators found - classified as general';
    }
    
    const modeConfig = this.modes[mode];
    const foundKeywords = modeConfig.keywords.filter(kw => 
      content.toLowerCase().includes(kw)
    );
    
    return `Classified as '${mode}' mode (score: ${score}) based on keywords: ${foundKeywords.join(', ')}`;
  }
}