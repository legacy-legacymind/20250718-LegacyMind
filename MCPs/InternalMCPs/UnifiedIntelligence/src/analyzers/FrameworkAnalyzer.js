/**
 * FrameworkAnalyzer - Determines which thinking frameworks might be applicable
 * 
 * Suggests frameworks based on content analysis
 */
export class FrameworkAnalyzer {
  constructor() {
    this.frameworks = {
      'first-principles': {
        name: 'First Principles Thinking',
        description: 'Break down problems to fundamental truths',
        triggers: {
          keywords: ['fundamental', 'basic', 'core', 'essential', 'principle', 'truth', 'assumption', 'why'],
          patterns: [
            /why.*work/i,
            /how.*really/i,
            /what.*if.*different/i,
            /fundamental.*problem/i,
            /basic.*principle/i
          ],
          contexts: ['complex-problem', 'design-challenge', 'assumptions']
        },
        confidence_threshold: 0.6
      },
      
      'six-hats': {
        name: 'Six Thinking Hats',
        description: 'Explore all perspectives systematically',
        triggers: {
          keywords: ['perspective', 'viewpoint', 'angle', 'opinion', 'feeling', 'emotion', 'risk', 'benefit'],
          patterns: [
            /different.*perspective/i,
            /how.*feel/i,
            /what.*risk/i,
            /benefit.*of/i,
            /creative.*solution/i
          ],
          contexts: ['decision-making', 'team-discussion', 'evaluation']
        },
        confidence_threshold: 0.5
      },
      
      'swot': {
        name: 'SWOT Analysis',
        description: 'Evaluate strengths, weaknesses, opportunities, threats',
        triggers: {
          keywords: ['strength', 'weakness', 'opportunity', 'threat', 'advantage', 'disadvantage', 'competition'],
          patterns: [
            /strength.*weakness/i,
            /opportunity.*threat/i,
            /competitive.*advantage/i,
            /internal.*external/i,
            /strategic.*analysis/i
          ],
          contexts: ['strategic-planning', 'competitive-analysis', 'project-evaluation']
        },
        confidence_threshold: 0.6
      },
      
      'root-cause': {
        name: 'Root Cause Analysis',
        description: 'Identify the fundamental cause of problems',
        triggers: {
          keywords: ['problem', 'issue', 'cause', 'root', 'why', 'symptom', 'source', 'origin'],
          patterns: [
            /root.*cause/i,
            /why.*happen/i,
            /cause.*of/i,
            /underlying.*issue/i,
            /real.*problem/i
          ],
          contexts: ['debugging', 'problem-solving', 'investigation']
        },
        confidence_threshold: 0.7
      },
      
      'pros-cons': {
        name: 'Pros and Cons Analysis',
        description: 'Systematic evaluation of advantages and disadvantages',
        triggers: {
          keywords: ['pros', 'cons', 'advantage', 'disadvantage', 'positive', 'negative', 'benefit', 'drawback'],
          patterns: [
            /pros.*cons/i,
            /advantage.*disadvantage/i,
            /positive.*negative/i,
            /benefit.*drawback/i,
            /good.*bad/i
          ],
          contexts: ['decision-making', 'evaluation', 'comparison']
        },
        confidence_threshold: 0.5
      },
      
      'design-thinking': {
        name: 'Design Thinking',
        description: 'Human-centered approach to innovation',
        triggers: {
          keywords: ['user', 'customer', 'empathy', 'prototype', 'test', 'iterate', 'solution', 'need'],
          patterns: [
            /user.*need/i,
            /customer.*want/i,
            /prototype.*test/i,
            /iterate.*improve/i,
            /human.*centered/i
          ],
          contexts: ['product-design', 'user-experience', 'innovation']
        },
        confidence_threshold: 0.6
      },
      
      'systems-thinking': {
        name: 'Systems Thinking',
        description: 'Understanding complex interconnections',
        triggers: {
          keywords: ['system', 'interconnect', 'relationship', 'pattern', 'feedback', 'loop', 'complex', 'holistic'],
          patterns: [
            /system.*thinking/i,
            /interconnect.*relationship/i,
            /feedback.*loop/i,
            /complex.*system/i,
            /holistic.*view/i
          ],
          contexts: ['complex-systems', 'architecture', 'strategy']
        },
        confidence_threshold: 0.7
      }
    };
    
    this.contextKeywords = {
      'decision-making': ['decide', 'choice', 'option', 'alternative', 'select', 'choose'],
      'problem-solving': ['problem', 'issue', 'challenge', 'difficulty', 'solve', 'fix'],
      'strategic-planning': ['strategy', 'plan', 'goal', 'objective', 'future', 'vision'],
      'analysis': ['analyze', 'examine', 'study', 'investigate', 'research', 'evaluate'],
      'design': ['design', 'create', 'build', 'develop', 'architect', 'structure'],
      'innovation': ['innovate', 'new', 'creative', 'original', 'breakthrough', 'invention']
    };
  }

  analyze(content, mode = null, tags = []) {
    const contentLower = content.toLowerCase();
    const suggestions = [];
    
    // Detect context
    const detectedContexts = this.detectContexts(contentLower);
    
    // Analyze each framework
    for (const [frameworkKey, framework] of Object.entries(this.frameworks)) {
      const score = this.calculateFrameworkScore(content, framework, detectedContexts, mode, tags);
      
      if (score.confidence >= framework.confidence_threshold) {
        suggestions.push({
          framework: frameworkKey,
          name: framework.name,
          description: framework.description,
          confidence: score.confidence,
          reasoning: score.reasoning,
          triggers: score.triggers,
          contexts: score.contexts
        });
      }
    }
    
    // Sort by confidence
    suggestions.sort((a, b) => b.confidence - a.confidence);
    
    return {
      suggestions: suggestions.slice(0, 3), // Top 3 suggestions
      totalEvaluated: Object.keys(this.frameworks).length,
      detectedContexts,
      confidence: suggestions.length > 0 ? suggestions[0].confidence : 0,
      reasoning: this.generateOverallReasoning(suggestions, detectedContexts),
      metadata: {
        contentLength: content.length,
        mode,
        tags: tags.slice(0, 5) // First 5 tags for context
      }
    };
  }
  
  calculateFrameworkScore(content, framework, contexts, mode, tags) {
    const contentLower = content.toLowerCase();
    let score = 0;
    let triggers = [];
    let reasoning = [];
    
    // Keyword matching
    let keywordMatches = 0;
    for (const keyword of framework.triggers.keywords) {
      if (contentLower.includes(keyword)) {
        keywordMatches++;
        triggers.push(`keyword: ${keyword}`);
      }
    }
    
    const keywordScore = Math.min(keywordMatches / framework.triggers.keywords.length, 1);
    score += keywordScore * 0.4;
    
    if (keywordMatches > 0) {
      reasoning.push(`${keywordMatches} keyword matches`);
    }
    
    // Pattern matching
    let patternMatches = 0;
    for (const pattern of framework.triggers.patterns) {
      if (pattern.test(content)) {
        patternMatches++;
        triggers.push(`pattern: ${pattern.source}`);
      }
    }
    
    const patternScore = Math.min(patternMatches / framework.triggers.patterns.length, 1);
    score += patternScore * 0.3;
    
    if (patternMatches > 0) {
      reasoning.push(`${patternMatches} pattern matches`);
    }
    
    // Context matching
    let contextMatches = 0;
    for (const context of framework.triggers.contexts) {
      if (contexts.includes(context)) {
        contextMatches++;
        triggers.push(`context: ${context}`);
      }
    }
    
    const contextScore = contextMatches > 0 ? 1 : 0;
    score += contextScore * 0.2;
    
    if (contextMatches > 0) {
      reasoning.push(`${contextMatches} context matches`);
    }
    
    // Mode alignment
    const modeScore = this.calculateModeAlignment(mode, framework);
    score += modeScore * 0.1;
    
    if (modeScore > 0) {
      reasoning.push(`mode alignment: ${modeScore}`);
    }
    
    // Normalize score
    const confidence = Math.min(score, 1);
    
    return {
      confidence,
      triggers,
      reasoning: reasoning.join('; '),
      contexts: contexts.filter(c => framework.triggers.contexts.includes(c)),
      scores: {
        keyword: keywordScore,
        pattern: patternScore,
        context: contextScore,
        mode: modeScore,
        total: confidence
      }
    };
  }
  
  detectContexts(contentLower) {
    const detectedContexts = [];
    
    for (const [context, keywords] of Object.entries(this.contextKeywords)) {
      const matches = keywords.filter(keyword => contentLower.includes(keyword));
      if (matches.length > 0) {
        detectedContexts.push(context);
      }
    }
    
    return detectedContexts;
  }
  
  calculateModeAlignment(mode, framework) {
    const modeAlignments = {
      'first-principles': {
        debug: 0.8,
        design: 0.9,
        question: 0.7,
        reflect: 0.6
      },
      'six-hats': {
        design: 0.8,
        question: 0.7,
        reflect: 0.9,
        execute: 0.6
      },
      'swot': {
        design: 0.8,
        reflect: 0.7,
        execute: 0.6
      },
      'root-cause': {
        debug: 0.9,
        question: 0.8,
        reflect: 0.7
      },
      'pros-cons': {
        design: 0.7,
        question: 0.6,
        reflect: 0.8
      },
      'design-thinking': {
        design: 0.9,
        execute: 0.8,
        explore: 0.7
      },
      'systems-thinking': {
        design: 0.8,
        reflect: 0.7,
        explore: 0.8
      }
    };
    
    if (!mode) return 0;
    
    const alignments = modeAlignments[framework.name];
    return alignments ? (alignments[mode] || 0) : 0;
  }
  
  generateOverallReasoning(suggestions, contexts) {
    const reasoning = [];
    
    if (suggestions.length === 0) {
      reasoning.push('No frameworks reached confidence threshold');
    } else {
      reasoning.push(`${suggestions.length} frameworks suggested`);
      
      if (suggestions.length > 0) {
        reasoning.push(`Top suggestion: ${suggestions[0].name} (${Math.round(suggestions[0].confidence * 100)}%)`);
      }
    }
    
    if (contexts.length > 0) {
      reasoning.push(`Detected contexts: ${contexts.join(', ')}`);
    }
    
    return reasoning.join('; ');
  }
}