/**
 * First Principles Thinking Framework
 * 
 * Break down complex problems into fundamental truths and build up
 * solutions from there, avoiding assumptions and analogies.
 */
export class FirstPrinciplesFramework {
  constructor() {
    this.name = 'First Principles Thinking';
    this.description = 'Break down problems to fundamental truths and rebuild from there';
  }
  
  getSteps() {
    return [
      {
        prompt: 'What is the problem or concept you want to understand from first principles?',
        guidance: 'Describe what you\'re trying to solve or understand.'
      },
      {
        prompt: 'What are the current assumptions or conventional approaches to this?',
        guidance: 'List how this is typically understood or solved. What does everyone "know" about it?'
      },
      {
        prompt: 'Break it down: What are the absolute fundamental truths or laws that apply?',
        guidance: 'Identify the basic facts that cannot be reduced further. Think physics, mathematics, or core principles.'
      },
      {
        prompt: 'What constraints are real vs. assumed? Which "rules" can be questioned?',
        guidance: 'Separate actual physical/logical constraints from artificial or historical ones.'
      },
      {
        prompt: 'Building up: Given only the fundamental truths, how could this work?',
        guidance: 'Start from the basics and construct a solution without relying on existing methods.'
      },
      {
        prompt: 'What novel approaches or insights emerge from this first principles analysis?',
        guidance: 'Identify new possibilities that weren\'t visible when thinking by analogy.'
      }
    ];
  }
  
  generateConclusion(responses) {
    const problem = responses.step_0?.response || 'Unknown problem';
    const fundamentals = responses.step_2?.response || 'No fundamentals identified';
    const novel = responses.step_5?.response || 'No novel insights';
    
    return {
      summary: `First Principles Analysis: ${problem}`,
      breakdown: {
        conventionalView: responses.step_1?.response || 'Not specified',
        fundamentalTruths: fundamentals,
        realConstraints: responses.step_3?.response || 'Not identified'
      },
      reconstruction: {
        newApproach: responses.step_4?.response || 'Not developed',
        novelInsights: novel
      },
      breakthrough: `By returning to fundamentals (${fundamentals}), we can see new possibilities: ${novel}`,
      timestamp: new Date().toISOString()
    };
  }
}