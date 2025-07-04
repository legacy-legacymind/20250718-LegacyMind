import { executionStrategies } from '../utils/executionStrategies.js';
import { logger } from '../utils/logger.js';
export const researchAndBuildTool = {
    name: 'research_and_build',
    description: 'Research a topic with GMCP and implement/build with CCMCP',
    schema: {
        type: 'object',
        properties: {
            topic: { type: 'string', description: 'Topic to research and implement' },
            researchQuery: { type: 'string', description: 'Specific research query for GMCP' },
            buildInstructions: { type: 'string', description: 'Build/implementation instructions for CCMCP' },
            executionMode: {
                type: 'string',
                enum: ['parallel', 'sequential'],
                description: 'Whether to run research and build in parallel or sequentially',
                default: 'sequential'
            },
            includeFileAnalysis: { type: 'boolean', description: 'Whether to include file analysis in research', default: false },
            filePaths: { type: 'array', items: { type: 'string' }, description: 'Files to analyze during research' }
        },
        required: ['topic', 'researchQuery', 'buildInstructions']
    },
    async handler(args, context) {
        const { topic, researchQuery, buildInstructions, executionMode, includeFileAnalysis, filePaths } = args;
        logger.info('Starting research and build task', { topic, executionMode });
        // Prepare GMCP task with file analysis if requested
        let gmcpTask = researchQuery;
        if (includeFileAnalysis && filePaths && filePaths.length > 0) {
            const fileAnalysis = filePaths.map((path) => `@${path}`).join(' ');
            gmcpTask = `${fileAnalysis} ${researchQuery}`;
        }
        const task = {
            type: 'research_and_build',
            title: `Research and Build: ${topic}`,
            description: `Research ${topic} and implement based on findings`,
            ccmcpTask: buildInstructions,
            gmcpTask,
            parallel: executionMode === 'parallel',
            aggregationStrategy: executionMode === 'sequential' ? 'custom' : 'merge',
        };
        const strategy = executionStrategies[executionMode === 'parallel' ? 'parallel' : 'sequential'];
        const result = await strategy.execute(task, context);
        logger.info('Research and build task completed', {
            topic,
            executionTime: result.executionTime,
            researchSuccess: result.gmcpResult?.success,
            buildSuccess: result.ccmcpResult?.success
        });
        return {
            success: true,
            task: {
                topic,
                executionMode,
                includeFileAnalysis,
                analyzedFiles: filePaths || [],
            },
            research: {
                success: result.gmcpResult?.success || false,
                data: result.gmcpResult?.data,
                error: result.gmcpResult?.error,
                executionTime: result.gmcpResult?.executionTime || 0,
            },
            build: {
                success: result.ccmcpResult?.success || false,
                data: result.ccmcpResult?.data,
                error: result.ccmcpResult?.error,
                executionTime: result.ccmcpResult?.executionTime || 0,
            },
            performance: {
                totalExecutionTime: result.executionTime,
                efficiency: executionMode === 'parallel' ? 'high' : 'sequential',
            },
        };
    }
};
//# sourceMappingURL=researchAndBuild.js.map