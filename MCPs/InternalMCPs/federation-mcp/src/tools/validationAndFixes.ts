import { FederationTool, TaskDefinition, FederationContext } from '../types/index.js';
import { executionStrategies } from '../utils/executionStrategies.js';
import { logger } from '../utils/logger.js';

export const validationAndFixesTool: FederationTool = {
  name: 'validation_and_fixes',
  description: 'Validate code/systems with GMCP and implement fixes with CCMCP',
  schema: {
    type: 'object',
    properties: {
      target: { type: 'string', description: 'Target to validate (code, system, configuration)' },
      filePaths: { type: 'array', items: { type: 'string' }, description: 'Files to validate' },
      validationCriteria: { type: 'string', description: 'Validation criteria and checks to perform' },
      fixInstructions: { type: 'string', description: 'Instructions for implementing fixes' },
      validationType: {
        type: 'string',
        enum: ['CODE_REVIEW', 'SECURITY_AUDIT', 'PERFORMANCE_CHECK', 'SYNTAX_VALIDATION', 'CUSTOM'],
        description: 'Type of validation to perform',
        default: 'CUSTOM'
      },
      autoFix: { type: 'boolean', description: 'Whether to automatically apply fixes', default: false },
      sandboxTest: { type: 'boolean', description: 'Whether to test fixes in sandbox', default: true }
    },
    required: ['target', 'validationCriteria', 'fixInstructions']
  },
  
  async handler(args: any, context: FederationContext) {
    const { target, filePaths, validationCriteria, fixInstructions, validationType, autoFix, sandboxTest } = args;
    
    logger.info('Starting validation and fixes task', { target, validationType, autoFix });

    // Prepare GMCP validation task
    let gmcpTask = `Validate ${target}: ${validationCriteria}`;
    if (filePaths && filePaths.length > 0) {
      const fileReferences = filePaths.map((path: string) => `@${path}`).join(' ');
      gmcpTask = `${fileReferences} ${gmcpTask}`;
    }

    // Add validation type context
    if (validationType !== 'CUSTOM') {
      gmcpTask += ` Focus on ${validationType.toLowerCase().replace('_', ' ')} aspects.`;
    }

    // Prepare CCMCP fix task
    let ccmcpTask = fixInstructions;
    if (autoFix) {
      ccmcpTask = `Automatically implement fixes: ${fixInstructions}`;
    } else {
      ccmcpTask = `Prepare fix recommendations: ${fixInstructions}`;
    }

    const task: TaskDefinition = {
      type: 'validation_and_fixes',
      title: `Validate and Fix: ${target}`,
      description: `Validate ${target} and implement necessary fixes`,
      ccmcpTask,
      gmcpTask,
      parallel: false, // Sequential: validate first, then fix
      aggregationStrategy: 'custom',
    };

    // Use sequential strategy so validation informs fixes
    const strategy = executionStrategies.sequential;
    const result = await strategy.execute(task, context);

    // If sandbox testing is enabled and we have fixes, test them
    let sandboxResults = null;
    if (sandboxTest && result.ccmcpResult?.success) {
      logger.debug('Running sandbox tests for fixes');
      try {
        sandboxResults = await context.gmcpManager.executeTask(
          `Test the following fixes: ${JSON.stringify(result.ccmcpResult.data)}`,
          undefined, // model
          true, // sandbox
          60000 // 1 minute timeout for sandbox
        );
      } catch (error) {
        logger.warn('Sandbox testing failed', { error });
      }
    }

    logger.info('Validation and fixes task completed', { 
      target,
      validationType,
      executionTime: result.executionTime,
      validationSuccess: result.gmcpResult?.success,
      fixesSuccess: result.ccmcpResult?.success,
      sandboxTestSuccess: sandboxResults?.success
    });

    return {
      success: true,
      task: {
        target,
        validationType,
        autoFix,
        sandboxTest,
        validatedFiles: filePaths || [],
        strategy: 'sequential',
      },
      validation: {
        success: result.gmcpResult?.success || false,
        data: result.gmcpResult?.data,
        error: result.gmcpResult?.error,
        executionTime: result.gmcpResult?.executionTime || 0,
        issues: extractIssues(result.gmcpResult?.data),
      },
      fixes: {
        success: result.ccmcpResult?.success || false,
        data: result.ccmcpResult?.data,
        error: result.ccmcpResult?.error,
        executionTime: result.ccmcpResult?.executionTime || 0,
        autoApplied: autoFix,
      },
      sandboxTest: sandboxResults ? {
        success: sandboxResults.success,
        data: sandboxResults.data,
        error: sandboxResults.error,
        executionTime: sandboxResults.executionTime,
      } : null,
      performance: {
        totalExecutionTime: result.executionTime,
        workflow: 'validation_then_fixes',
      },
    };
  }
};

function extractIssues(validationData: any): string[] {
    if (!validationData || typeof validationData !== 'object') {
      return [];
    }

    const issues: string[] = [];
    
    // Extract issues from validation data
    if (validationData.output && typeof validationData.output === 'string') {
      const lines = validationData.output.split('\n');
      const issueLines = lines.filter((line: string) => 
        line.includes('error') || 
        line.includes('warning') || 
        line.includes('issue') || 
        line.includes('problem') ||
        line.includes('fix') ||
        line.includes('todo')
      );
      issues.push(...issueLines.slice(0, 10)); // Top 10 issues
    }

    return issues;
}