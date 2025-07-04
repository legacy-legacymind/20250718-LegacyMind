import { spawn } from 'child_process';
import { GMCPManager as IGMCPManager, TaskResult } from '../types/index.js';
import { logger } from '../utils/logger.js';

export class GMCPManager implements IGMCPManager {
  private defaultTimeout: number;

  constructor(defaultTimeout: number = 300000) {
    this.defaultTimeout = defaultTimeout;
  }

  async executeTask(
    prompt: string,
    model?: string,
    sandbox?: boolean,
    timeout?: number
  ): Promise<TaskResult> {
    const startTime = Date.now();
    const actualTimeout = timeout || this.defaultTimeout;

    logger.debug('Executing GMCP task', {
      promptLength: prompt.length,
      model,
      sandbox,
      timeout: actualTimeout,
    });

    return new Promise((resolve) => {
      const timeoutId = setTimeout(() => {
        logger.warn('GMCP task timed out', { timeout: actualTimeout });
        resolve({
          success: false,
          error: `Task timed out after ${actualTimeout}ms`,
          executionTime: Date.now() - startTime,
          source: 'gmcp',
        });
      }, actualTimeout);

      try {
        const args = ['-p', prompt];
        
        if (model) {
          args.push('-m', model);
        }
        
        if (sandbox) {
          args.push('-s');
        }

        const geminiProcess = spawn('gemini', args, {
          stdio: ['ignore', 'pipe', 'pipe'],
        });

        let stdout = '';
        let stderr = '';

        geminiProcess.stdout.on('data', (data) => {
          stdout += data.toString();
        });

        geminiProcess.stderr.on('data', (data) => {
          stderr += data.toString();
        });

        geminiProcess.on('close', (code) => {
          clearTimeout(timeoutId);
          
          if (code === 0) {
            logger.debug('GMCP task completed successfully');
            resolve({
              success: true,
              data: {
                output: stdout,
                model: model || 'default',
                sandbox: sandbox || false,
                timestamp: new Date().toISOString(),
              },
              executionTime: Date.now() - startTime,
              source: 'gmcp',
            });
          } else {
            logger.error('GMCP task failed', { code, stderr });
            resolve({
              success: false,
              error: `Gemini process exited with code ${code}: ${stderr}`,
              executionTime: Date.now() - startTime,
              source: 'gmcp',
            });
          }
        });

        geminiProcess.on('error', (error) => {
          clearTimeout(timeoutId);
          logger.error('GMCP process error', { error: error.message });
          resolve({
            success: false,
            error: `Failed to start Gemini process: ${error.message}`,
            executionTime: Date.now() - startTime,
            source: 'gmcp',
          });
        });
      } catch (error) {
        clearTimeout(timeoutId);
        const errorMessage = error instanceof Error ? error.message : String(error);
        logger.error('GMCP task setup failed', { error: errorMessage });
        resolve({
          success: false,
          error: errorMessage,
          executionTime: Date.now() - startTime,
          source: 'gmcp',
        });
      }
    });
  }

  async ping(): Promise<boolean> {
    try {
      const result = await this.executeTask('ping', undefined, false, 10000);
      return result.success;
    } catch (error) {
      logger.error('GMCP ping failed', { error });
      return false;
    }
  }

  async analyzeFile(filePath: string, analysis: string, timeout?: number): Promise<TaskResult> {
    const prompt = `@${filePath} ${analysis}`;
    return this.executeTask(prompt, undefined, false, timeout);
  }

  async sandboxTest(code: string, timeout?: number): Promise<TaskResult> {
    return this.executeTask(code, undefined, true, timeout);
  }
}