/**
 * Framework Engine - Manages and executes thinking frameworks
 * 
 * This engine loads available frameworks and provides a unified interface
 * for applying them to thoughts
 */
import { FirstPrinciplesFramework } from './first-principles.js';
import { SixThinkingHatsFramework } from './six-hats.js';
import { SwotFramework } from './swot.js';

export class FrameworkEngine {
  constructor() {
    this.frameworks = new Map();
    this.activeFrameworks = new Map(); // Track active framework sessions
    
    // Initialize built-in frameworks
    this.registerFramework('first-principles', new FirstPrinciplesFramework());
    this.registerFramework('six-hats', new SixThinkingHatsFramework());
    this.registerFramework('swot', new SwotFramework());
  }
  
  registerFramework(key, framework) {
    if (!framework.name || !framework.getSteps || !framework.generateConclusion) {
      throw new Error('Invalid framework: must have name, getSteps, and generateConclusion methods');
    }
    
    this.frameworks.set(key, framework);
    console.log(`Registered framework: ${key} - ${framework.name}`);
  }
  
  getAvailableFrameworks() {
    const available = [];
    
    for (const [key, framework] of this.frameworks) {
      available.push({
        key,
        name: framework.name,
        description: framework.description || 'No description available',
        stepCount: framework.getSteps().length
      });
    }
    
    return available;
  }
  
  getFramework(key) {
    return this.frameworks.get(key);
  }
  
  async applyFramework(frameworkKey, options = {}) {
    // Direct framework application for ui_think tool
    const framework = this.frameworks.get(frameworkKey);
    if (!framework) {
      throw new Error(`Framework ${frameworkKey} not found`);
    }
    
    // Create a temporary session for direct application
    const sessionKey = `direct-${Date.now()}`;
    const sessionId = options.sessionId || 'direct-application';
    
    // Start the framework
    this.startFramework(sessionId, frameworkKey, options.thoughtId);
    
    return {
      frameworkKey,
      frameworkName: framework.name,
      applied: true,
      sessionKey: `${sessionId}-${frameworkKey}`,
      content: options.content
    };
  }
  
  startFramework(sessionId, frameworkKey, thoughtId = null) {
    const framework = this.frameworks.get(frameworkKey);
    
    if (!framework) {
      throw new Error(`Framework not found: ${frameworkKey}`);
    }
    
    const steps = framework.getSteps();
    const frameworkSession = {
      sessionId,
      frameworkKey,
      framework,
      thoughtId,
      startedAt: new Date().toISOString(),
      currentStep: 0,
      totalSteps: steps.length,
      steps,
      responses: {},
      metadata: {
        frameworkName: framework.name,
        frameworkDescription: framework.description
      },
      status: 'active'
    };
    
    const sessionKey = `${sessionId}:${frameworkKey}`;
    this.activeFrameworks.set(sessionKey, frameworkSession);
    
    return {
      sessionKey,
      frameworkKey,
      frameworkName: framework.name,
      currentStep: 0,
      totalSteps: steps.length,
      step: steps[0],
      status: 'started'
    };
  }
  
  getCurrentStep(sessionKey) {
    const session = this.activeFrameworks.get(sessionKey);
    
    if (!session) {
      throw new Error(`No active framework session: ${sessionKey}`);
    }
    
    if (session.currentStep >= session.totalSteps) {
      return {
        sessionKey,
        complete: true,
        status: 'completed'
      };
    }
    
    return {
      sessionKey,
      frameworkKey: session.frameworkKey,
      frameworkName: session.metadata.frameworkName,
      currentStep: session.currentStep,
      totalSteps: session.totalSteps,
      step: session.steps[session.currentStep],
      status: 'active'
    };
  }
  
  submitStepResponse(sessionKey, response) {
    const session = this.activeFrameworks.get(sessionKey);
    
    if (!session) {
      throw new Error(`No active framework session: ${sessionKey}`);
    }
    
    if (session.status === 'completed') {
      throw new Error('Framework session already completed');
    }
    
    // Store the response
    const stepKey = `step_${session.currentStep}`;
    session.responses[stepKey] = {
      response,
      timestamp: new Date().toISOString(),
      stepNumber: session.currentStep,
      prompt: session.steps[session.currentStep].prompt
    };
    
    // Move to next step
    session.currentStep++;
    
    // Check if completed
    if (session.currentStep >= session.totalSteps) {
      return this.completeFramework(sessionKey);
    }
    
    // Return next step
    return {
      sessionKey,
      frameworkKey: session.frameworkKey,
      frameworkName: session.metadata.frameworkName,
      currentStep: session.currentStep,
      totalSteps: session.totalSteps,
      step: session.steps[session.currentStep],
      status: 'active',
      progress: Math.round((session.currentStep / session.totalSteps) * 100)
    };
  }
  
  completeFramework(sessionKey) {
    const session = this.activeFrameworks.get(sessionKey);
    
    if (!session) {
      throw new Error(`No active framework session: ${sessionKey}`);
    }
    
    // Generate conclusion
    const conclusion = session.framework.generateConclusion(session.responses);
    
    // Mark as completed
    session.status = 'completed';
    session.completedAt = new Date().toISOString();
    session.conclusion = conclusion;
    
    // Calculate duration
    const startTime = new Date(session.startedAt).getTime();
    const endTime = new Date(session.completedAt).getTime();
    session.durationMs = endTime - startTime;
    
    // Return completion result
    const result = {
      sessionKey,
      frameworkKey: session.frameworkKey,
      frameworkName: session.metadata.frameworkName,
      status: 'completed',
      conclusion,
      responses: session.responses,
      metadata: {
        thoughtId: session.thoughtId,
        sessionId: session.sessionId,
        startedAt: session.startedAt,
        completedAt: session.completedAt,
        durationMs: session.durationMs,
        stepCount: session.totalSteps
      }
    };
    
    // Remove from active sessions after a delay (keep for retrieval)
    setTimeout(() => {
      this.activeFrameworks.delete(sessionKey);
    }, 300000); // 5 minutes
    
    return result;
  }
  
  abandonFramework(sessionKey) {
    const session = this.activeFrameworks.get(sessionKey);
    
    if (!session) {
      return { status: 'not_found', sessionKey };
    }
    
    session.status = 'abandoned';
    session.abandonedAt = new Date().toISOString();
    
    // Remove from active sessions
    this.activeFrameworks.delete(sessionKey);
    
    return {
      sessionKey,
      frameworkKey: session.frameworkKey,
      frameworkName: session.metadata.frameworkName,
      status: 'abandoned',
      completedSteps: session.currentStep,
      totalSteps: session.totalSteps,
      responses: session.responses
    };
  }
  
  getActiveFrameworks(sessionId = null) {
    const active = [];
    
    for (const [sessionKey, session] of this.activeFrameworks) {
      if (!sessionId || session.sessionId === sessionId) {
        active.push({
          sessionKey,
          frameworkKey: session.frameworkKey,
          frameworkName: session.metadata.frameworkName,
          currentStep: session.currentStep,
          totalSteps: session.totalSteps,
          status: session.status,
          startedAt: session.startedAt,
          progress: Math.round((session.currentStep / session.totalSteps) * 100)
        });
      }
    }
    
    return active;
  }
  
  // Quick apply - for simple, non-interactive framework application
  async quickApply(frameworkKey, responses) {
    const framework = this.frameworks.get(frameworkKey);
    
    if (!framework) {
      throw new Error(`Framework not found: ${frameworkKey}`);
    }
    
    const steps = framework.getSteps();
    
    // Validate responses match steps
    const expectedKeys = steps.map((_, idx) => `step_${idx}`);
    const providedKeys = Object.keys(responses);
    
    const missingKeys = expectedKeys.filter(key => !providedKeys.includes(key));
    if (missingKeys.length > 0) {
      throw new Error(`Missing responses for steps: ${missingKeys.join(', ')}`);
    }
    
    // Generate conclusion
    const conclusion = framework.generateConclusion(responses);
    
    return {
      frameworkKey,
      frameworkName: framework.name,
      conclusion,
      responses,
      metadata: {
        quickApply: true,
        timestamp: new Date().toISOString()
      }
    };
  }
}