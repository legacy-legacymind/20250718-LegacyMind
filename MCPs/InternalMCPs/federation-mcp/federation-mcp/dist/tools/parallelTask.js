import { executionStrategies } from '../utils/executionStrategies.js';
import { logger } from '../utils/logger.js';
export const parallelTaskTool = {
    name: 'parallel_task',
    description: 'Execute a task using both CCMCP and GMCP agents in parallel',
    schema: {
        type: 'object',
        properties: {
            title: { type: 'string', description: 'Title of the task' },
            description: { type: 'string', description: 'Description of the task' },
            ccmcpTask: { type: 'string', description: 'Task prompt for CCMCP (Claude Code)' },
            gmcpTask: { type: 'string', description: 'Task prompt for GMCP (Gemini)' },
            aggregationStrategy: {
                type: 'string',
                enum: ['merge', 'prioritize_ccmcp', 'prioritize_gmcp'],
                description: 'How to combine results from both agents',
                default: 'merge'
            },
            executionStrategy: {
                type: 'string',
                enum: ['parallel', 'sequential'],
                description: 'Whether to run tasks in parallel or sequentially',
                default: 'parallel'
            }
        },
        required: ['title', 'description']
    },
    async handler(args, context) {
        const { title, description, ccmcpTask, gmcpTask, aggregationStrategy, executionStrategy } = args;
        if (!ccmcpTask && !gmcpTask) {
            throw new Error('At least one of ccmcpTask or gmcpTask must be provided');
        }
        const task = {
            type: 'custom',
            title,
            description,
            ccmcpTask,
            gmcpTask,
            parallel: executionStrategy === 'parallel',
            aggregationStrategy: aggregationStrategy || 'merge',
        };
        logger.info('Executing parallel task', { title, strategy: executionStrategy });
        const strategy = executionStrategies[executionStrategy === 'sequential' ? 'sequential' : 'parallel'];
        const result = await strategy.execute(task, context);
        logger.info('Parallel task completed', {
            title,
            executionTime: result.executionTime,
            ccmcpSuccess: result.ccmcpResult?.success,
            gmcpSuccess: result.gmcpResult?.success
        });
        return {
            success: true,
            task: {
                title,
                description,
                strategy: executionStrategy,
                aggregationStrategy,
            },
            results: result,
            performance: {
                totalExecutionTime: result.executionTime,
                ccmcpExecutionTime: result.ccmcpResult?.executionTime || 0,
                gmcpExecutionTime: result.gmcpResult?.executionTime || 0,
            },
        };
    }
};
//# sourceMappingURL=parallelTask.js.map