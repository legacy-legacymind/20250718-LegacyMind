/**
 * Analyzer Orchestrator - Coordinates all analysis components
 */
import { ModeAnalyzer } from './ModeAnalyzer.js';
import { SignificanceAnalyzer } from './SignificanceAnalyzer.js';
import { TagAnalyzer } from './TagAnalyzer.js';
import { FrameworkAnalyzer } from './FrameworkAnalyzer.js';

export class AnalyzerOrchestrator {
  constructor() {
    this.modeAnalyzer = new ModeAnalyzer();
    this.significanceAnalyzer = new SignificanceAnalyzer();
    this.tagAnalyzer = new TagAnalyzer();
    this.frameworkAnalyzer = new FrameworkAnalyzer();
  }

  async analyzeThought(content, options = {}) {
    const startTime = Date.now();
    
    try {
      // Run all analyzers in parallel for efficiency
      const [
        modeResult,
        significanceResult,
        tagResult
      ] = await Promise.all([
        Promise.resolve(this.modeAnalyzer.analyze(content)),
        Promise.resolve(this.significanceAnalyzer.analyze(content)),
        Promise.resolve(this.tagAnalyzer.analyze(content))
      ]);
      
      // Run framework analyzer with context from other analyzers
      const frameworkResult = await Promise.resolve(
        this.frameworkAnalyzer.analyze(
          content,
          modeResult.mode,
          tagResult.tags
        )
      );
      
      const processingTime = Date.now() - startTime;
      
      // Combine results
      const analysis = {
        content,
        mode: modeResult.mode,
        significance: significanceResult.significance,
        tags: tagResult.tags,
        frameworks: frameworkResult.suggestions,
        
        // Detailed results
        analysis: {
          mode: modeResult,
          significance: significanceResult,
          tags: tagResult,
          frameworks: frameworkResult
        },
        
        // Summary metrics
        metrics: {
          processingTimeMs: processingTime,
          totalTags: tagResult.tags.length,
          detectedContexts: frameworkResult.detectedContexts,
          topFramework: frameworkResult.suggestions[0]?.framework || null,
          overallConfidence: this.calculateOverallConfidence(
            modeResult,
            significanceResult,
            tagResult,
            frameworkResult
          )
        },
        
        // Metadata
        metadata: {
          timestamp: new Date().toISOString(),
          version: '3.0.0',
          options,
          contentStats: {
            length: content.length,
            wordCount: content.split(/\s+/).length,
            sentences: content.split(/[.!?]+/).length - 1
          }
        }
      };
      
      return analysis;
      
    } catch (error) {
      console.error('Error in thought analysis:', error);
      
      // Return fallback analysis
      return {
        content,
        mode: 'general',
        significance: 1,
        tags: [],
        frameworks: [],
        
        analysis: {
          error: error.message,
          fallback: true
        },
        
        metrics: {
          processingTimeMs: Date.now() - startTime,
          totalTags: 0,
          detectedContexts: [],
          topFramework: null,
          overallConfidence: 0
        },
        
        metadata: {
          timestamp: new Date().toISOString(),
          version: '3.0.0',
          error: true,
          options
        }
      };
    }
  }
  
  calculateOverallConfidence(modeResult, significanceResult, tagResult, frameworkResult) {
    const confidences = [
      modeResult.confidence || 0,
      significanceResult.confidence || 0,
      tagResult.confidence || 0,
      frameworkResult.confidence || 0
    ];
    
    // Weighted average (mode and significance are more important)
    const weights = [0.3, 0.3, 0.2, 0.2];
    const weightedSum = confidences.reduce((sum, conf, idx) => sum + (conf * weights[idx]), 0);
    
    return Math.round(weightedSum * 100) / 100;
  }
  
  // Utility method for quick mode-only analysis
  async analyzeMode(content) {
    return this.modeAnalyzer.analyze(content);
  }
  
  // Utility method for quick significance-only analysis
  async analyzeSignificance(content) {
    return this.significanceAnalyzer.analyze(content);
  }
  
  // Utility method for quick tag-only analysis
  async analyzeTags(content) {
    return this.tagAnalyzer.analyze(content);
  }
  
  // Utility method for quick framework-only analysis
  async analyzeFrameworks(content, mode = null, tags = []) {
    return this.frameworkAnalyzer.analyze(content, mode, tags);
  }
}

// Export individual analyzers as well
export {
  ModeAnalyzer,
  SignificanceAnalyzer,
  TagAnalyzer,
  FrameworkAnalyzer
};