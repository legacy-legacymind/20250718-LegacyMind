import { ExecutionStrategy, TaskDefinition, FederationContext, ParallelTaskResult } from '../types/index.js';
export declare class ParallelExecutionStrategy implements ExecutionStrategy {
    name: string;
    execute(task: TaskDefinition, context: FederationContext): Promise<ParallelTaskResult>;
    private aggregateResults;
    private createSummary;
}
export declare class FallbackExecutionStrategy implements ExecutionStrategy {
    name: string;
    execute(task: TaskDefinition, context: FederationContext): Promise<ParallelTaskResult>;
}
export declare class SequentialExecutionStrategy implements ExecutionStrategy {
    name: string;
    execute(task: TaskDefinition, context: FederationContext): Promise<ParallelTaskResult>;
}
export declare const executionStrategies: {
    parallel: ParallelExecutionStrategy;
    fallback: FallbackExecutionStrategy;
    sequential: SequentialExecutionStrategy;
};
//# sourceMappingURL=executionStrategies.d.ts.map