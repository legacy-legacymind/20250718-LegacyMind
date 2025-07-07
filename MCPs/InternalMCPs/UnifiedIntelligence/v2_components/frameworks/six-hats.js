/**
 * Six Thinking Hats Framework
 * 
 * Edward de Bono's method for exploring different perspectives by
 * "wearing" different colored hats representing different thinking modes.
 */
export class SixThinkingHatsFramework {
  constructor() {
    this.name = 'Six Thinking Hats';
    this.description = 'Explore all angles of a decision through six distinct thinking modes';
  }
  
  getSteps() {
    return [
      {
        prompt: 'What decision, problem, or idea do you want to explore?',
        guidance: 'Clearly state what you\'re analyzing.'
      },
      {
        prompt: '⚪ WHITE HAT (Facts): What are the facts, data, and information available?',
        guidance: 'Be objective. List only verifiable facts and data, no interpretations.'
      },
      {
        prompt: '🔴 RED HAT (Emotions): What are your gut feelings and emotional reactions?',
        guidance: 'Express feelings, hunches, and intuitions without justification.'
      },
      {
        prompt: '⚫ BLACK HAT (Caution): What could go wrong? What are the risks and downsides?',
        guidance: 'Be critical but logical. Identify weaknesses and potential problems.'
      },
      {
        prompt: '🟡 YELLOW HAT (Optimism): What are the benefits and positive outcomes?',
        guidance: 'Focus on value, benefits, and why it might work. Be optimistic but realistic.'
      },
      {
        prompt: '🟢 GREEN HAT (Creativity): What are creative alternatives and new possibilities?',
        guidance: 'Think laterally. Generate new ideas, alternatives, and creative solutions.'
      },
      {
        prompt: '🔵 BLUE HAT (Process): Synthesize all perspectives. What\'s the best path forward?',
        guidance: 'Step back and integrate all the thinking. What conclusions can you draw?'
      }
    ];
  }
  
  generateConclusion(responses) {
    const topic = responses.step_0?.response || 'Unknown topic';
    
    return {
      summary: `Six Hats Analysis: ${topic}`,
      perspectives: {
        facts: responses.step_1?.response || 'No facts provided',
        emotions: responses.step_2?.response || 'No emotions expressed',
        risks: responses.step_3?.response || 'No risks identified',
        benefits: responses.step_4?.response || 'No benefits identified',
        alternatives: responses.step_5?.response || 'No alternatives generated'
      },
      synthesis: responses.step_6?.response || 'No synthesis provided',
      balancedView: 'This analysis provided a 360-degree view by systematically exploring facts, feelings, cautions, benefits, creative alternatives, and overall process.',
      timestamp: new Date().toISOString()
    };
  }
}