/**
 * SWOT Analysis Framework
 * 
 * Strategic planning tool that evaluates Strengths, Weaknesses,
 * Opportunities, and Threats.
 */
export class SwotFramework {
  constructor() {
    this.name = 'SWOT Analysis';
    this.description = 'Evaluate Strengths, Weaknesses, Opportunities, and Threats systematically';
  }
  
  getSteps() {
    return [
      {
        prompt: 'What project, decision, or situation do you want to analyze?',
        guidance: 'Describe what you\'re evaluating. Be specific about scope and context.'
      },
      {
        prompt: 'STRENGTHS: What internal advantages or positive attributes exist?',
        guidance: 'List internal factors that give an advantage. Think resources, skills, assets, competitive advantages.'
      },
      {
        prompt: 'WEAKNESSES: What internal limitations or negative factors exist?',
        guidance: 'Identify internal factors that could be improved. Consider gaps, limitations, resource constraints.'
      },
      {
        prompt: 'OPPORTUNITIES: What external factors could be advantageous?',
        guidance: 'Look for external trends, changes, or circumstances you could exploit. Think market, technology, social changes.'
      },
      {
        prompt: 'THREATS: What external factors could cause problems?',
        guidance: 'Identify external risks, competition, or changes that could negatively impact. Consider worst-case scenarios.'
      },
      {
        prompt: 'STRATEGIES: How can you use strengths to capture opportunities and minimize threats?',
        guidance: 'Connect your strengths to opportunities (SO strategies) and to counter threats (ST strategies).'
      },
      {
        prompt: 'IMPROVEMENTS: How can you address weaknesses to capture opportunities and avoid threats?',
        guidance: 'Plan how to overcome weaknesses for opportunities (WO strategies) and to avoid threats (WT strategies).'
      }
    ];
  }
  
  generateConclusion(responses) {
    const subject = responses.step_0?.response || 'Unknown subject';
    
    const swotMatrix = {
      strengths: responses.step_1?.response || 'None identified',
      weaknesses: responses.step_2?.response || 'None identified',
      opportunities: responses.step_3?.response || 'None identified',
      threats: responses.step_4?.response || 'None identified'
    };
    
    const strategies = {
      leverageStrengths: responses.step_5?.response || 'No strategies developed',
      addressWeaknesses: responses.step_6?.response || 'No improvements identified'
    };
    
    return {
      summary: `SWOT Analysis: ${subject}`,
      matrix: swotMatrix,
      strategies: strategies,
      keyInsight: this.generateKeyInsight(swotMatrix),
      actionPlan: 'Based on this analysis, prioritize leveraging strengths for opportunities while addressing critical weaknesses that expose you to threats.',
      timestamp: new Date().toISOString()
    };
  }
  
  generateKeyInsight(matrix) {
    // Simple heuristic to generate an insight
    const hasStrengths = matrix.strengths !== 'None identified';
    const hasOpportunities = matrix.opportunities !== 'None identified';
    
    if (hasStrengths && hasOpportunities) {
      return 'Strong position: Multiple strengths align with external opportunities.';
    } else if (!hasStrengths && matrix.threats !== 'None identified') {
      return 'Vulnerable position: Lack of strengths combined with external threats requires immediate action.';
    } else {
      return 'Mixed position: Focus on building strengths and seeking new opportunities.';
    }
  }
}