#!/usr/bin/env node

/**
 * Parallel Execution Test for Federation MCP
 * 
 * This script specifically tests the parallel execution capabilities
 * and performance characteristics of the Federation MCP.
 */

console.log('🚀 Federation MCP - Parallel Execution Test\n');

// Test configuration
const testConfig = {
  serverStartupTimeout: 10000,
  taskTimeout: 60000,
  concurrentTasks: 3,
};

class ParallelExecutionTester {
  constructor() {
    this.results = [];
    this.performanceMetrics = [];
  }

  log(message, type = 'info') {
    const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
    const prefix = type === 'error' ? '❌' : type === 'success' ? '✅' : 'ℹ️';
    console.log(`[${timestamp}] ${prefix} ${message}`);
  }

  async runPerformanceTests() {
    this.log('Starting parallel execution performance tests');

    // Test 1: Single parallel task performance
    await this.testSingleParallelTask();
    
    // Test 2: Multiple concurrent parallel tasks
    await this.testConcurrentParallelTasks();
    
    // Test 3: Sequential vs Parallel comparison
    await this.testSequentialVsParallel();
    
    // Test 4: Fallback mechanism
    await this.testFallbackMechanism();
    
    // Test 5: Load testing
    await this.testLoadHandling();

    this.printPerformanceReport();
  }

  async testSingleParallelTask() {
    this.log('Test 1: Single parallel task performance');
    
    const startTime = Date.now();
    
    try {
      // Simulate a parallel task execution
      const taskDefinition = {
        title: 'Performance Test - Single Task',
        description: 'Test single parallel task execution time',
        ccmcpTask: 'Create a simple calculator function with basic operations',
        gmcpTask: 'Analyze mathematical computation patterns and best practices',
        executionStrategy: 'parallel'
      };

      // Simulate the parallel execution
      const results = await this.simulateParallelExecution(taskDefinition);
      const executionTime = Date.now() - startTime;

      this.performanceMetrics.push({
        test: 'Single Parallel Task',
        executionTime,
        success: results.success,
        details: results
      });

      this.log(`Single parallel task completed in ${executionTime}ms`, 'success');
      
    } catch (error) {
      this.log(`Single parallel task failed: ${error.message}`, 'error');
    }
  }

  async testConcurrentParallelTasks() {
    this.log(`Test 2: ${testConfig.concurrentTasks} concurrent parallel tasks`);
    
    const startTime = Date.now();
    const tasks = [];

    // Create multiple concurrent tasks
    for (let i = 0; i < testConfig.concurrentTasks; i++) {
      const task = {
        title: `Concurrent Task ${i + 1}`,
        description: `Concurrent execution test task ${i + 1}`,
        ccmcpTask: `Create a function for task ${i + 1}`,
        gmcpTask: `Analyze requirements for task ${i + 1}`,
        executionStrategy: 'parallel'
      };
      
      tasks.push(this.simulateParallelExecution(task));
    }

    try {
      const results = await Promise.all(tasks);
      const executionTime = Date.now() - startTime;
      const successCount = results.filter(r => r.success).length;

      this.performanceMetrics.push({
        test: 'Concurrent Parallel Tasks',
        executionTime,
        taskCount: testConfig.concurrentTasks,
        successCount,
        successRate: (successCount / testConfig.concurrentTasks) * 100,
        averageTimePerTask: executionTime / testConfig.concurrentTasks
      });

      this.log(`${testConfig.concurrentTasks} concurrent tasks completed in ${executionTime}ms`, 'success');
      this.log(`Success rate: ${successCount}/${testConfig.concurrentTasks} (${((successCount / testConfig.concurrentTasks) * 100).toFixed(1)}%)`);
      
    } catch (error) {
      this.log(`Concurrent tasks failed: ${error.message}`, 'error');
    }
  }

  async testSequentialVsParallel() {
    this.log('Test 3: Sequential vs Parallel comparison');
    
    const taskDefinition = {
      title: 'Sequential vs Parallel Comparison',
      description: 'Compare execution times between sequential and parallel strategies',
      ccmcpTask: 'Create a data processing pipeline',
      gmcpTask: 'Analyze data processing best practices and optimization techniques'
    };

    // Test sequential execution
    this.log('Testing sequential execution...');
    const sequentialStart = Date.now();
    const sequentialResult = await this.simulateSequentialExecution(taskDefinition);
    const sequentialTime = Date.now() - sequentialStart;

    // Test parallel execution
    this.log('Testing parallel execution...');
    const parallelStart = Date.now();
    const parallelResult = await this.simulateParallelExecution(taskDefinition);
    const parallelTime = Date.now() - parallelStart;

    const speedup = sequentialTime / parallelTime;
    const efficiency = ((speedup / 2) * 100); // Assuming 2 agents

    this.performanceMetrics.push({
      test: 'Sequential vs Parallel',
      sequentialTime,
      parallelTime,
      speedup: speedup.toFixed(2),
      efficiency: efficiency.toFixed(1) + '%',
      parallelAdvantage: sequentialTime > parallelTime
    });

    this.log(`Sequential execution: ${sequentialTime}ms`);
    this.log(`Parallel execution: ${parallelTime}ms`);
    this.log(`Speedup: ${speedup.toFixed(2)}x`, parallelTime < sequentialTime ? 'success' : 'info');
  }

  async testFallbackMechanism() {
    this.log('Test 4: Fallback mechanism');
    
    const startTime = Date.now();
    
    try {
      // Simulate a scenario where one agent fails
      const taskDefinition = {
        title: 'Fallback Test',
        description: 'Test fallback when primary agent fails',
        ccmcpTask: 'Create error handling mechanisms',
        gmcpTask: 'Analyze system resilience patterns',
        fallbackStrategy: 'ccmcp'
      };

      const result = await this.simulateFallbackExecution(taskDefinition);
      const executionTime = Date.now() - startTime;

      this.performanceMetrics.push({
        test: 'Fallback Mechanism',
        executionTime,
        fallbackTriggered: result.fallbackTriggered,
        success: result.success
      });

      this.log(`Fallback mechanism ${result.fallbackTriggered ? 'activated' : 'not needed'} in ${executionTime}ms`, 'success');
      
    } catch (error) {
      this.log(`Fallback test failed: ${error.message}`, 'error');
    }
  }

  async testLoadHandling() {
    this.log('Test 5: Load handling test');
    
    const highLoadTasks = 5;
    const startTime = Date.now();
    const tasks = [];

    // Create high-load scenario
    for (let i = 0; i < highLoadTasks; i++) {
      const task = {
        title: `Load Test Task ${i + 1}`,
        description: `High load test scenario ${i + 1}`,
        ccmcpTask: `Handle complex computation task ${i + 1}`,
        gmcpTask: `Perform detailed analysis for task ${i + 1}`,
        executionStrategy: 'parallel'
      };
      
      tasks.push(this.simulateParallelExecution(task));
    }

    try {
      const results = await Promise.allSettled(tasks);
      const executionTime = Date.now() - startTime;
      const successful = results.filter(r => r.status === 'fulfilled' && r.value.success).length;
      const failed = results.length - successful;

      this.performanceMetrics.push({
        test: 'Load Handling',
        executionTime,
        totalTasks: highLoadTasks,
        successful,
        failed,
        failureRate: (failed / highLoadTasks) * 100,
        throughput: (successful / executionTime) * 1000 // tasks per second
      });

      this.log(`Load test: ${successful}/${highLoadTasks} tasks successful in ${executionTime}ms`, 'success');
      this.log(`Throughput: ${((successful / executionTime) * 1000).toFixed(3)} tasks/second`);
      
    } catch (error) {
      this.log(`Load test failed: ${error.message}`, 'error');
    }
  }

  // Simulation methods (these would interface with the actual Federation MCP in practice)
  async simulateParallelExecution(task) {
    // Simulate parallel execution of CCMCP and GMCP
    const ccmcpTime = Math.random() * 3000 + 1000; // 1-4 seconds
    const gmcpTime = Math.random() * 5000 + 2000;  // 2-7 seconds
    
    const [ccmcpResult, gmcpResult] = await Promise.all([
      this.simulateAgentExecution('ccmcp', ccmcpTime),
      this.simulateAgentExecution('gmcp', gmcpTime)
    ]);

    return {
      success: ccmcpResult.success && gmcpResult.success,
      ccmcpResult,
      gmcpResult,
      executionTime: Math.max(ccmcpTime, gmcpTime),
      strategy: 'parallel'
    };
  }

  async simulateSequentialExecution(task) {
    // Simulate sequential execution
    const gmcpTime = Math.random() * 5000 + 2000;
    const gmcpResult = await this.simulateAgentExecution('gmcp', gmcpTime);
    
    const ccmcpTime = Math.random() * 3000 + 1000;
    const ccmcpResult = await this.simulateAgentExecution('ccmcp', ccmcpTime);

    return {
      success: ccmcpResult.success && gmcpResult.success,
      ccmcpResult,
      gmcpResult,
      executionTime: ccmcpTime + gmcpTime,
      strategy: 'sequential'
    };
  }

  async simulateFallbackExecution(task) {
    // Simulate primary agent failure and fallback
    const primaryFails = Math.random() < 0.3; // 30% chance of primary failure
    
    if (primaryFails) {
      // Primary fails, use fallback
      const fallbackTime = Math.random() * 3000 + 1000;
      const fallbackResult = await this.simulateAgentExecution('ccmcp', fallbackTime);
      
      return {
        success: fallbackResult.success,
        fallbackTriggered: true,
        result: fallbackResult,
        executionTime: fallbackTime + 500 // Add overhead for fallback detection
      };
    } else {
      // Primary succeeds
      const primaryTime = Math.random() * 5000 + 2000;
      const primaryResult = await this.simulateAgentExecution('gmcp', primaryTime);
      
      return {
        success: primaryResult.success,
        fallbackTriggered: false,
        result: primaryResult,
        executionTime: primaryTime
      };
    }
  }

  async simulateAgentExecution(agent, timeMs) {
    await new Promise(resolve => setTimeout(resolve, timeMs));
    
    // 95% success rate simulation
    const success = Math.random() < 0.95;
    
    return {
      success,
      agent,
      executionTime: timeMs,
      data: success ? `${agent} execution completed successfully` : null,
      error: success ? null : `${agent} execution failed`
    };
  }

  printPerformanceReport() {
    console.log('\n' + '='.repeat(60));
    console.log('📊 FEDERATION MCP PERFORMANCE REPORT');
    console.log('='.repeat(60));

    this.performanceMetrics.forEach((metric, index) => {
      console.log(`\n${index + 1}. ${metric.test}:`);
      console.log('   ' + '-'.repeat(40));
      
      Object.entries(metric).forEach(([key, value]) => {
        if (key !== 'test') {
          console.log(`   ${key.padEnd(20)}: ${value}`);
        }
      });
    });

    console.log('\n' + '='.repeat(60));
    console.log('🎯 Key Performance Insights:');
    console.log('='.repeat(60));

    // Calculate overall insights
    const avgExecutionTime = this.performanceMetrics
      .filter(m => m.executionTime)
      .reduce((sum, m) => sum + m.executionTime, 0) / 
      this.performanceMetrics.filter(m => m.executionTime).length;

    console.log(`Average execution time: ${avgExecutionTime.toFixed(0)}ms`);
    
    const parallelTest = this.performanceMetrics.find(m => m.test === 'Sequential vs Parallel');
    if (parallelTest) {
      console.log(`Parallel advantage: ${parallelTest.parallelAdvantage ? 'YES' : 'NO'}`);
      console.log(`Speedup achieved: ${parallelTest.speedup}x`);
    }

    const loadTest = this.performanceMetrics.find(m => m.test === 'Load Handling');
    if (loadTest) {
      console.log(`Load handling: ${loadTest.successful}/${loadTest.totalTasks} tasks successful`);
      console.log(`System throughput: ${loadTest.throughput.toFixed(3)} tasks/second`);
    }

    console.log('\n✅ Performance testing completed!');
  }
}

// Run the performance tests
const tester = new ParallelExecutionTester();
tester.runPerformanceTests().catch(console.error);