export interface FederationConfig {
  ccmcpTimeout: number;
  gmcpTimeout: number;
  parallelTimeout: number;
  fallbackEnabled: boolean;
  debugMode: boolean;
}

export interface TaskResult {
  success: boolean;
  data?: any;
  error?: string;
  executionTime: number;
  source: 'ccmcp' | 'gmcp' | 'parallel';
}

export interface ParallelTaskResult {
  ccmcpResult?: TaskResult;
  gmcpResult?: TaskResult;
  aggregatedResult?: any;
  executionTime: number;
  strategy: 'parallel' | 'fallback' | 'primary';
}

export interface FederationTool {
  name: string;
  description: string;
  handler: (args: any, context: FederationContext) => Promise<any>;
  schema: any;
}

export interface FederationContext {
  config: FederationConfig;
  ccmcpManager: CCMCPManager;
  gmcpManager: GMCPManager;
}

export interface CCMCPManager {
  executeTask(description: string, prompt: string, timeout?: number): Promise<TaskResult>;
}

export interface GMCPManager {
  executeTask(prompt: string, model?: string, sandbox?: boolean, timeout?: number): Promise<TaskResult>;
}

export interface TaskDefinition {
  type: 'research_and_build' | 'analyze_and_document' | 'validation_and_fixes' | 'large_file_analysis' | 'custom';
  title: string;
  description: string;
  ccmcpTask?: string;
  gmcpTask?: string;
  parallel?: boolean;
  fallbackStrategy?: 'ccmcp' | 'gmcp' | 'none';
  aggregationStrategy?: 'merge' | 'prioritize_ccmcp' | 'prioritize_gmcp' | 'custom';
}

export interface AggregationStrategy {
  name: string;
  handler: (ccmcpResult: TaskResult, gmcpResult: TaskResult) => any;
}

export interface ExecutionStrategy {
  name: string;
  execute: (task: TaskDefinition, context: FederationContext) => Promise<ParallelTaskResult>;
}