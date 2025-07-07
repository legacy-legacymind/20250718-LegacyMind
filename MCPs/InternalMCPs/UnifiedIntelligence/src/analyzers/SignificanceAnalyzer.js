/**
 * SignificanceAnalyzer - Evaluates the importance and impact of thoughts
 * 
 * Significance scale: 1-10 (low to high)
 */
export class SignificanceAnalyzer {
  constructor() {
    this.significanceFactors = {
      // High significance indicators
      breakthrough: {
        keywords: ['breakthrough', 'insight', 'discovery', 'realization', 'eureka', 'aha', 'epiphany'],
        weight: 3,
        baseScore: 8
      },
      decision: {
        keywords: ['decide', 'decision', 'choose', 'select', 'determine', 'conclude', 'resolve'],
        weight: 2,
        baseScore: 6
      },
      problem: {
        keywords: ['problem', 'issue', 'challenge', 'difficulty', 'obstacle', 'blocker', 'critical'],
        weight: 2,
        baseScore: 7
      },
      solution: {
        keywords: ['solution', 'fix', 'resolve', 'answer', 'solve', 'approach', 'method'],
        weight: 2,
        baseScore: 6
      },
      learning: {
        keywords: ['learned', 'understand', 'knowledge', 'skill', 'master', 'grasp', 'comprehend'],
        weight: 1.5,
        baseScore: 5
      },
      
      // Medium significance indicators
      action: {
        keywords: ['implement', 'build', 'create', 'develop', 'execute', 'perform', 'action'],
        weight: 1,
        baseScore: 4
      },
      analysis: {
        keywords: ['analyze', 'examine', 'investigate', 'study', 'research', 'explore'],
        weight: 1,
        baseScore: 3
      },
      
      // Low significance indicators
      routine: {
        keywords: ['routine', 'normal', 'regular', 'standard', 'typical', 'usual', 'common'],
        weight: 0.5,
        baseScore: 2
      },
      observation: {
        keywords: ['notice', 'observe', 'see', 'watch', 'look', 'view', 'note'],
        weight: 0.5,
        baseScore: 2
      }
    };
    
    this.modifiers = {
      // Urgency modifiers
      urgent: {
        keywords: ['urgent', 'immediate', 'asap', 'critical', 'emergency', 'now', 'quickly'],
        modifier: 1.5
      },
      
      // Impact modifiers
      major: {
        keywords: ['major', 'significant', 'important', 'crucial', 'vital', 'essential', 'key'],
        modifier: 1.3
      },
      
      // Uncertainty modifiers
      uncertain: {
        keywords: ['maybe', 'perhaps', 'possibly', 'might', 'could', 'uncertain', 'unclear'],
        modifier: 0.8
      },
      
      // Negation modifiers
      negation: {
        keywords: ['not', 'no', 'never', 'none', 'nothing', 'neither', 'nor'],
        modifier: 0.9
      }
    };
  }

  analyze(content) {
    const contentLower = content.toLowerCase();
    let significance = 1; // Base significance
    let reasoning = [];
    let detectedFactors = [];
    
    // Analyze significance factors
    for (const [factor, config] of Object.entries(this.significanceFactors)) {
      const matches = config.keywords.filter(keyword => 
        contentLower.includes(keyword)
      );
      
      if (matches.length > 0) {
        const factorScore = config.baseScore * config.weight * matches.length;
        significance = Math.max(significance, factorScore);
        
        detectedFactors.push({
          factor,
          matches,
          score: factorScore,
          baseScore: config.baseScore,
          weight: config.weight
        });
        
        reasoning.push(`${factor} indicators: ${matches.join(', ')} (score: ${factorScore})`);
      }
    }
    
    // Apply modifiers
    let finalModifier = 1;
    let appliedModifiers = [];
    
    for (const [modifier, config] of Object.entries(this.modifiers)) {
      const matches = config.keywords.filter(keyword => 
        contentLower.includes(keyword)
      );
      
      if (matches.length > 0) {
        finalModifier *= config.modifier;
        appliedModifiers.push({
          modifier,
          matches,
          multiplier: config.modifier
        });
        
        reasoning.push(`${modifier} modifier: ${matches.join(', ')} (×${config.modifier})`);
      }
    }
    
    // Apply final modifier and ensure bounds
    significance = Math.max(1, Math.min(10, significance * finalModifier));
    
    // Length-based adjustment (longer thoughts tend to be more significant)
    const lengthFactor = Math.min(1.2, 1 + (content.length / 1000));
    significance *= lengthFactor;
    
    // Final bounds check
    significance = Math.max(1, Math.min(10, significance));
    
    return {
      significance: Math.round(significance * 10) / 10, // Round to 1 decimal
      confidence: this.calculateConfidence(detectedFactors, appliedModifiers),
      factors: detectedFactors,
      modifiers: appliedModifiers,
      reasoning: reasoning.join('; '),
      metadata: {
        contentLength: content.length,
        lengthFactor,
        finalModifier
      }
    };
  }
  
  calculateConfidence(factors, modifiers) {
    // Confidence based on number of detected factors and their clarity
    const factorCount = factors.length;
    const modifierCount = modifiers.length;
    
    if (factorCount === 0) return 0.3; // Low confidence if no factors
    if (factorCount === 1) return 0.6; // Medium confidence for single factor
    if (factorCount >= 2) return 0.8; // High confidence for multiple factors
    
    // Boost confidence if modifiers are present
    return Math.min(0.9, 0.8 + (modifierCount * 0.1));
  }
}