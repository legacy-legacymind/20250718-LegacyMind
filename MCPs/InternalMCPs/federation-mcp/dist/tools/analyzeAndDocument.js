import { executionStrategies } from '../utils/executionStrategies.js';
import { logger } from '../utils/logger.js';
export const analyzeAndDocumentTool = {
    name: 'analyze_and_document',
    description: 'Analyze codebase/files with GMCP and create documentation with CCMCP',
    schema: {
        type: 'object',
        properties: {
            target: { type: 'string', description: 'Target to analyze (codebase, files, etc.)' },
            filePaths: { type: 'array', items: { type: 'string' }, description: 'Specific files to analyze' },
            analysisPrompt: { type: 'string', description: 'Analysis instructions for GMCP' },
            documentationPrompt: { type: 'string', description: 'Documentation creation instructions for CCMCP' },
            documentationType: {
                type: 'string',
                enum: ['README', 'API_DOCS', 'TECHNICAL_GUIDE', 'USER_GUIDE', 'CUSTOM'],
                description: 'Type of documentation to create',
                default: 'CUSTOM'
            },
            outputFormat: {
                type: 'string',
                enum: ['markdown', 'html', 'json', 'plain_text'],
                description: 'Output format for documentation',
                default: 'markdown'
            }
        },
        required: ['target', 'analysisPrompt', 'documentationPrompt']
    },
    async handler(args, context) {
        const { target, filePaths, analysisPrompt, documentationPrompt, documentationType, outputFormat } = args;
        logger.info('Starting analyze and document task', { target, documentationType });
        // Prepare GMCP analysis task with file references
        let gmcpTask = analysisPrompt;
        if (filePaths && filePaths.length > 0) {
            const fileReferences = filePaths.map((path) => `@${path}`).join(' ');
            gmcpTask = `${fileReferences} ${analysisPrompt}`;
        }
        // Prepare CCMCP documentation task
        let ccmcpTask = documentationPrompt;
        if (documentationType !== 'CUSTOM') {
            ccmcpTask = `Create ${documentationType} documentation: ${documentationPrompt}`;
        }
        if (outputFormat !== 'markdown') {
            ccmcpTask += ` Output format: ${outputFormat}`;
        }
        const task = {
            type: 'analyze_and_document',
            title: `Analyze and Document: ${target}`,
            description: `Analyze ${target} and create ${documentationType} documentation`,
            ccmcpTask,
            gmcpTask,
            parallel: false, // Sequential makes more sense for analysis -> documentation
            aggregationStrategy: 'custom',
        };
        // Use sequential strategy so analysis informs documentation
        const strategy = executionStrategies.sequential;
        const result = await strategy.execute(task, context);
        logger.info('Analyze and document task completed', {
            target,
            documentationType,
            executionTime: result.executionTime,
            analysisSuccess: result.gmcpResult?.success,
            documentationSuccess: result.ccmcpResult?.success
        });
        return {
            success: true,
            task: {
                target,
                documentationType,
                outputFormat,
                analyzedFiles: filePaths || [],
                strategy: 'sequential',
            },
            analysis: {
                success: result.gmcpResult?.success || false,
                data: result.gmcpResult?.data,
                error: result.gmcpResult?.error,
                executionTime: result.gmcpResult?.executionTime || 0,
                insights: extractInsights(result.gmcpResult?.data),
            },
            documentation: {
                success: result.ccmcpResult?.success || false,
                data: result.ccmcpResult?.data,
                error: result.ccmcpResult?.error,
                executionTime: result.ccmcpResult?.executionTime || 0,
                format: outputFormat,
            },
            performance: {
                totalExecutionTime: result.executionTime,
                workflow: 'analysis_first_then_documentation',
            },
        };
    }
};
function extractInsights(analysisData) {
    if (!analysisData || typeof analysisData !== 'object') {
        return [];
    }
    const insights = [];
    // Extract key insights from analysis data
    if (analysisData.output && typeof analysisData.output === 'string') {
        // Simple heuristic to extract insights
        const lines = analysisData.output.split('\n');
        const insightLines = lines.filter((line) => line.includes('key') ||
            line.includes('important') ||
            line.includes('note') ||
            line.includes('insight'));
        insights.push(...insightLines.slice(0, 5)); // Top 5 insights
    }
    return insights;
}
//# sourceMappingURL=analyzeAndDocument.js.map