import { GMCPManager as IGMCPManager, TaskResult } from '../types/index.js';
export declare class GMCPManager implements IGMCPManager {
    private defaultTimeout;
    constructor(defaultTimeout?: number);
    executeTask(prompt: string, model?: string, sandbox?: boolean, timeout?: number): Promise<TaskResult>;
    ping(): Promise<boolean>;
    analyzeFile(filePath: string, analysis: string, timeout?: number): Promise<TaskResult>;
    sandboxTest(code: string, timeout?: number): Promise<TaskResult>;
}
//# sourceMappingURL=GMCPManager.d.ts.map