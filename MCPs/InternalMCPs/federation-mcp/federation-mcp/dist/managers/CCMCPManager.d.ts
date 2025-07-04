import { CCMCPManager as ICCMCPManager, TaskResult } from '../types/index.js';
export declare class CCMCPManager implements ICCMCPManager {
    private defaultTimeout;
    constructor(defaultTimeout?: number);
    executeTask(description: string, prompt: string, timeout?: number): Promise<TaskResult>;
    private simulateTaskExecution;
    ping(): Promise<boolean>;
}
//# sourceMappingURL=CCMCPManager.d.ts.map