/**
 * TagAnalyzer - Extracts relevant tags from thought content
 * 
 * Tags help categorize and retrieve thoughts later
 */
export class TagAnalyzer {
  constructor() {
    this.tagCategories = {
      // Technical tags
      technology: {
        keywords: ['javascript', 'python', 'nodejs', 'react', 'vue', 'angular', 'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'redis', 'postgresql', 'mongodb', 'api', 'rest', 'graphql', 'microservices'],
        prefix: 'tech-'
      },
      
      // Process tags
      process: {
        keywords: ['planning', 'testing', 'debugging', 'deployment', 'architecture', 'design', 'refactoring', 'optimization', 'security', 'performance'],
        prefix: 'process-'
      },
      
      // Domain tags
      domain: {
        keywords: ['frontend', 'backend', 'fullstack', 'devops', 'mobile', 'web', 'database', 'machine learning', 'ai', 'data science', 'blockchain', 'iot'],
        prefix: 'domain-'
      },
      
      // Concept tags
      concept: {
        keywords: ['pattern', 'principle', 'best practice', 'anti-pattern', 'methodology', 'framework', 'library', 'tool', 'convention', 'standard'],
        prefix: 'concept-'
      },
      
      // State tags
      state: {
        keywords: ['todo', 'doing', 'blocked', 'done', 'review', 'testing', 'deployed', 'archived'],
        prefix: 'state-'
      },
      
      // Priority tags
      priority: {
        keywords: ['urgent', 'high', 'medium', 'low', 'critical', 'important', 'nice-to-have'],
        prefix: 'priority-'
      },
      
      // Emotion tags
      emotion: {
        keywords: ['excited', 'frustrated', 'confused', 'confident', 'worried', 'satisfied', 'curious', 'motivated'],
        prefix: 'emotion-'
      }
    };
    
    // Common entity patterns
    this.entityPatterns = {
      // URLs
      url: /https?:\/\/[^\s]+/gi,
      
      // File paths
      filepath: /[\/\\]?(?:[a-zA-Z0-9_.-]+[\/\\])*[a-zA-Z0-9_.-]+\.[a-zA-Z0-9]{1,4}/g,
      
      // Code-like patterns
      function: /function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)/gi,
      class: /class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)/gi,
      variable: /(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)/gi,
      
      // Version numbers
      version: /v?\d+\.\d+(?:\.\d+)?/gi,
      
      // Hashtags
      hashtag: /#[a-zA-Z0-9_]+/gi,
      
      // Mentions
      mention: /@[a-zA-Z0-9_]+/gi
    };
  }

  analyze(content) {
    const tags = new Set();
    const contentLower = content.toLowerCase();
    const entities = {};
    
    // Extract category-based tags
    for (const [category, config] of Object.entries(this.tagCategories)) {
      const categoryTags = [];
      
      for (const keyword of config.keywords) {
        if (contentLower.includes(keyword)) {
          const tag = config.prefix + keyword.replace(/\s+/g, '-');
          tags.add(tag);
          categoryTags.push(tag);
        }
      }
      
      if (categoryTags.length > 0) {
        entities[category] = categoryTags;
      }
    }
    
    // Extract entity-based tags
    for (const [entityType, pattern] of Object.entries(this.entityPatterns)) {
      const matches = content.match(pattern);
      if (matches) {
        entities[entityType] = matches.slice(0, 5); // Limit to first 5 matches
        
        // Add simplified tags
        matches.slice(0, 3).forEach(match => {
          const simplifiedTag = this.simplifyEntity(entityType, match);
          if (simplifiedTag) {
            tags.add(simplifiedTag);
          }
        });
      }
    }
    
    // Extract implicit tags from content analysis
    const implicitTags = this.extractImplicitTags(content);
    implicitTags.forEach(tag => tags.add(tag));
    
    // Extract context-based tags
    const contextTags = this.extractContextTags(content);
    contextTags.forEach(tag => tags.add(tag));
    
    const tagArray = Array.from(tags).sort();
    
    return {
      tags: tagArray,
      entities,
      confidence: this.calculateConfidence(tagArray, entities),
      reasoning: this.generateReasoning(tagArray, entities),
      metadata: {
        totalTags: tagArray.length,
        categoryDistribution: this.getCategoryDistribution(tagArray),
        entityCount: Object.keys(entities).length
      }
    };
  }
  
  simplifyEntity(entityType, match) {
    switch (entityType) {
      case 'url':
        try {
          const url = new URL(match);
          return `site-${url.hostname.replace(/\./g, '-')}`;
        } catch {
          return null;
        }
      
      case 'filepath':
        const extension = match.split('.').pop();
        return extension ? `file-${extension}` : null;
      
      case 'function':
      case 'class':
      case 'variable':
        return `code-${entityType}`;
      
      case 'version':
        return 'versioned';
      
      case 'hashtag':
        return match.toLowerCase();
      
      case 'mention':
        return match.toLowerCase();
      
      default:
        return null;
    }
  }
  
  extractImplicitTags(content) {
    const tags = [];
    const contentLower = content.toLowerCase();
    
    // Question detection
    if (content.includes('?')) {
      tags.push('question');
    }
    
    // Decision detection
    if (contentLower.includes('decide') || contentLower.includes('choice')) {
      tags.push('decision');
    }
    
    // Problem detection
    if (contentLower.includes('problem') || contentLower.includes('issue')) {
      tags.push('problem');
    }
    
    // Solution detection
    if (contentLower.includes('solution') || contentLower.includes('fix')) {
      tags.push('solution');
    }
    
    // Learning detection
    if (contentLower.includes('learn') || contentLower.includes('understand')) {
      tags.push('learning');
    }
    
    // Idea detection
    if (contentLower.includes('idea') || contentLower.includes('concept')) {
      tags.push('idea');
    }
    
    return tags;
  }
  
  extractContextTags(content) {
    const tags = [];
    const contentLower = content.toLowerCase();
    
    // Time-based context
    const timeWords = ['today', 'tomorrow', 'yesterday', 'next week', 'last month'];
    if (timeWords.some(word => contentLower.includes(word))) {
      tags.push('time-sensitive');
    }
    
    // Collaboration context
    const collabWords = ['team', 'meeting', 'discuss', 'collaborate', 'review'];
    if (collabWords.some(word => contentLower.includes(word))) {
      tags.push('collaboration');
    }
    
    // Research context
    const researchWords = ['research', 'investigate', 'study', 'analyze', 'explore'];
    if (researchWords.some(word => contentLower.includes(word))) {
      tags.push('research');
    }
    
    // Documentation context
    const docWords = ['document', 'write', 'note', 'record', 'explain'];
    if (docWords.some(word => contentLower.includes(word))) {
      tags.push('documentation');
    }
    
    return tags;
  }
  
  calculateConfidence(tags, entities) {
    const tagCount = tags.length;
    const entityCount = Object.keys(entities).length;
    
    if (tagCount === 0) return 0.2;
    if (tagCount <= 2) return 0.5;
    if (tagCount <= 5) return 0.7;
    if (tagCount <= 10) return 0.8;
    return 0.9;
  }
  
  generateReasoning(tags, entities) {
    const reasoning = [];
    
    if (tags.length > 0) {
      reasoning.push(`Extracted ${tags.length} tags from content analysis`);
    }
    
    if (Object.keys(entities).length > 0) {
      reasoning.push(`Identified ${Object.keys(entities).length} entity types`);
    }
    
    const categoryCount = this.getCategoryDistribution(tags);
    if (Object.keys(categoryCount).length > 0) {
      reasoning.push(`Spans ${Object.keys(categoryCount).length} tag categories`);
    }
    
    return reasoning.join('; ') || 'No specific reasoning available';
  }
  
  getCategoryDistribution(tags) {
    const distribution = {};
    
    for (const tag of tags) {
      const category = tag.includes('-') ? tag.split('-')[0] : 'general';
      distribution[category] = (distribution[category] || 0) + 1;
    }
    
    return distribution;
  }
}