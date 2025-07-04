import { ExecutionStrategy, TaskDefinition, FederationContext, ParallelTaskResult, TaskResult } from '../types/index.js';
import { logger } from './logger.js';

export class ParallelExecutionStrategy implements ExecutionStrategy {
  name = 'parallel';

  async execute(task: TaskDefinition, context: FederationContext): Promise<ParallelTaskResult> {
    const startTime = Date.now();
    const { ccmcpManager, gmcpManager, config } = context;

    logger.debug('Starting parallel execution', { task: task.title });

    const promises: Promise<TaskResult>[] = [];
    const results: { ccmcpResult?: TaskResult; gmcpResult?: TaskResult } = {};

    // Execute CCMCP task if defined
    if (task.ccmcpTask) {
      const ccmcpPromise = ccmcpManager.executeTask(task.title, task.ccmcpTask, config.ccmcpTimeout)
        .then(result => {
          results.ccmcpResult = result;
          return result;
        });
      promises.push(ccmcpPromise);
    }

    // Execute GMCP task if defined
    if (task.gmcpTask) {
      const gmcpPromise = gmcpManager.executeTask(task.gmcpTask, undefined, false, config.gmcpTimeout)
        .then(result => {
          results.gmcpResult = result;
          return result;
        });
      promises.push(gmcpPromise);
    }

    // Wait for all tasks to complete or timeout
    try {
      await Promise.allSettled(promises);
    } catch (error) {
      logger.error('Parallel execution encountered error', { error });
    }

    const executionTime = Date.now() - startTime;
    
    // Aggregate results based on strategy
    const aggregatedResult = this.aggregateResults(results.ccmcpResult, results.gmcpResult, task.aggregationStrategy);

    return {
      ccmcpResult: results.ccmcpResult,
      gmcpResult: results.gmcpResult,
      aggregatedResult,
      executionTime,
      strategy: 'parallel',
    };
  }

  private aggregateResults(ccmcpResult?: TaskResult, gmcpResult?: TaskResult, strategy?: string): any {
    if (!ccmcpResult && !gmcpResult) {
      return { error: 'No results from either agent' };
    }

    switch (strategy) {
      case 'prioritize_ccmcp':
        return ccmcpResult?.success ? ccmcpResult.data : gmcpResult?.data;
      
      case 'prioritize_gmcp':
        return gmcpResult?.success ? gmcpResult.data : ccmcpResult?.data;
      
      case 'merge':
      default:
        return {
          ccmcp: ccmcpResult?.success ? ccmcpResult.data : { error: ccmcpResult?.error },
          gmcp: gmcpResult?.success ? gmcpResult.data : { error: gmcpResult?.error },
          summary: this.createSummary(ccmcpResult, gmcpResult),
        };
    }
  }

  private createSummary(ccmcpResult?: TaskResult, gmcpResult?: TaskResult): any {
    const summary: any = {
      ccmcp_success: ccmcpResult?.success || false,
      gmcp_success: gmcpResult?.success || false,
      ccmcp_time: ccmcpResult?.executionTime || 0,
      gmcp_time: gmcpResult?.executionTime || 0,
    };

    if (summary.ccmcp_success && summary.gmcp_success) {
      summary.status = 'both_successful';
    } else if (summary.ccmcp_success || summary.gmcp_success) {
      summary.status = 'partial_success';
    } else {
      summary.status = 'both_failed';
    }

    return summary;
  }
}

export class FallbackExecutionStrategy implements ExecutionStrategy {
  name = 'fallback';

  async execute(task: TaskDefinition, context: FederationContext): Promise<ParallelTaskResult> {
    const startTime = Date.now();
    const { ccmcpManager, gmcpManager, config } = context;

    logger.debug('Starting fallback execution', { 
      task: task.title, 
      fallbackStrategy: task.fallbackStrategy 
    });

    let primaryResult: TaskResult;
    let fallbackResult: TaskResult | undefined;

    // Determine primary agent
    const primaryIsGMCP = task.fallbackStrategy === 'gmcp';
    
    if (primaryIsGMCP && task.gmcpTask) {
      primaryResult = await gmcpManager.executeTask(task.gmcpTask, undefined, false, config.gmcpTimeout);
      
      // If primary fails and fallback is enabled, try CCMCP
      if (!primaryResult.success && config.fallbackEnabled && task.ccmcpTask) {
        logger.debug('Primary GMCP failed, falling back to CCMCP');
        fallbackResult = await ccmcpManager.executeTask(task.title, task.ccmcpTask, config.ccmcpTimeout);
      }
    } else if (task.ccmcpTask) {
      primaryResult = await ccmcpManager.executeTask(task.title, task.ccmcpTask, config.ccmcpTimeout);
      
      // If primary fails and fallback is enabled, try GMCP
      if (!primaryResult.success && config.fallbackEnabled && task.gmcpTask) {
        logger.debug('Primary CCMCP failed, falling back to GMCP');
        fallbackResult = await gmcpManager.executeTask(task.gmcpTask, undefined, false, config.gmcpTimeout);
      }
    } else {
      throw new Error('No valid tasks defined for fallback execution');
    }

    const executionTime = Date.now() - startTime;

    return {
      ccmcpResult: primaryIsGMCP ? fallbackResult : primaryResult,
      gmcpResult: primaryIsGMCP ? primaryResult : fallbackResult,
      aggregatedResult: (fallbackResult?.success ? fallbackResult.data : primaryResult.data),
      executionTime,
      strategy: 'fallback',
    };
  }
}

export class SequentialExecutionStrategy implements ExecutionStrategy {
  name = 'sequential';

  async execute(task: TaskDefinition, context: FederationContext): Promise<ParallelTaskResult> {
    const startTime = Date.now();
    const { ccmcpManager, gmcpManager, config } = context;

    logger.debug('Starting sequential execution', { task: task.title });

    let ccmcpResult: TaskResult | undefined;
    let gmcpResult: TaskResult | undefined;

    // Execute GMCP first (for analysis), then CCMCP (for implementation)
    if (task.gmcpTask) {
      gmcpResult = await gmcpManager.executeTask(task.gmcpTask, undefined, false, config.gmcpTimeout);
    }

    if (task.ccmcpTask) {
      // Pass GMCP result to CCMCP task if available
      let ccmcpPrompt = task.ccmcpTask;
      if (gmcpResult?.success) {
        ccmcpPrompt += `\n\nPrevious analysis result: ${JSON.stringify(gmcpResult.data)}`;
      }
      ccmcpResult = await ccmcpManager.executeTask(task.title, ccmcpPrompt, config.ccmcpTimeout);
    }

    const executionTime = Date.now() - startTime;

    return {
      ccmcpResult,
      gmcpResult,
      aggregatedResult: {
        analysis: gmcpResult?.data,
        implementation: ccmcpResult?.data,
        workflow: 'sequential',
      },
      executionTime,
      strategy: 'fallback', // This uses fallback typing but implements sequential
    };
  }
}

export const executionStrategies = {
  parallel: new ParallelExecutionStrategy(),
  fallback: new FallbackExecutionStrategy(),
  sequential: new SequentialExecutionStrategy(),
};