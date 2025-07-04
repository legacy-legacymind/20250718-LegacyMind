#!/usr/bin/env node

// Test script for Phase 1 UnifiedWorkflow features
// Run with: node test-phase1.js

import { spawn } from 'child_process';
import { promisify } from 'util';
import { setTimeout } from 'timers/promises';

const sleep = promisify(setTimeout);

async function testUnifiedWorkflow() {
  console.log('=== Testing UnifiedWorkflow Phase 1 Features ===\n');

  // Test data
  const testProject = {
    name: 'Federation Infrastructure Phase 1',
    description: 'Implement project and documentation management tools',
    owner: 'CCD',
    objectives: [
      'Add uw_projects tool',
      'Add uw_system_docs tool',
      'Maintain three-tier architecture'
    ],
    budget: 50000,
    start_date: '2025-07-03',
    end_date: '2025-07-17'
  };

  const testDoc = {
    title: 'UnifiedWorkflow Phase 1 Implementation Guide',
    content: 'This document describes the implementation of project and documentation management tools...',
    category: 'implementation',
    valid_from: '2025-07-03',
    created_by: 'CCD'
  };

  // Test cases
  const tests = [
    // Project tests
    {
      name: 'Create Project',
      tool: 'uw_projects',
      action: 'create',
      data: testProject
    },
    {
      name: 'Query All Projects',
      tool: 'uw_projects',
      action: 'query',
      data: {}
    },
    {
      name: 'Add Member to Project',
      tool: 'uw_projects',
      action: 'add_member',
      data: {
        project_id: 'PROJECT_ID_PLACEHOLDER',
        member: 'CCI',
        role: 'developer'
      }
    },
    {
      name: 'Link Ticket to Project',
      tool: 'uw_projects',
      action: 'link_ticket',
      data: {
        project_id: 'PROJECT_ID_PLACEHOLDER',
        ticket_id: '20250703-CCD-gxzw61'
      }
    },
    
    // Documentation tests
    {
      name: 'Create Documentation',
      tool: 'uw_system_docs',
      action: 'create',
      data: testDoc
    },
    {
      name: 'Query All Docs',
      tool: 'uw_system_docs',
      action: 'query',
      data: {}
    },
    {
      name: 'Update Documentation',
      tool: 'uw_system_docs',
      action: 'update',
      data: {
        doc_id: 'DOC_ID_PLACEHOLDER',
        content: testDoc.content + '\n\n## Update\nAdded implementation details.',
        updated_by: 'CCD'
      }
    },
    {
      name: 'Add Reference',
      tool: 'uw_system_docs',
      action: 'add_reference',
      data: {
        doc_id: 'DOC_ID_PLACEHOLDER',
        reference: 'https://github.com/legacymind/unified-workflow'
      }
    }
  ];

  let projectId = null;
  let docId = null;

  console.log('Starting tests...\n');

  for (const test of tests) {
    // Replace placeholders with actual IDs
    if (test.data.project_id === 'PROJECT_ID_PLACEHOLDER' && projectId) {
      test.data.project_id = projectId;
    }
    if (test.data.doc_id === 'DOC_ID_PLACEHOLDER' && docId) {
      test.data.doc_id = docId;
    }

    console.log(`Test: ${test.name}`);
    console.log(`Tool: ${test.tool}`);
    console.log(`Action: ${test.action}`);
    console.log(`Data: ${JSON.stringify(test.data, null, 2)}`);
    
    try {
      // Simulate MCP tool call
      const result = await simulateMCPCall(test.tool, test.action, test.data);
      console.log(`Result: ${JSON.stringify(result, null, 2)}`);
      
      // Extract IDs for subsequent tests
      if (test.name === 'Create Project' && result.project) {
        projectId = result.project.project_id;
      }
      if (test.name === 'Create Documentation' && result.doc) {
        docId = result.doc.doc_id;
      }
      
      console.log('✅ Test passed\n');
    } catch (error) {
      console.log(`❌ Test failed: ${error.message}\n`);
    }

    await sleep(100); // Small delay between tests
  }

  console.log('=== All tests completed ===');
}

// Simulate MCP tool call (in real usage, this would go through the MCP protocol)
async function simulateMCPCall(tool, action, data) {
  // This is a placeholder - in production, you'd use the actual MCP client
  console.log('(This would call the MCP server with the tool request)');
  return {
    success: true,
    message: 'Simulated response',
    [tool.includes('project') ? 'project' : 'doc']: {
      ...data,
      [`${tool.includes('project') ? 'project' : 'doc'}_id`]: `20250703-CCD-${Math.random().toString(36).substr(2, 6)}`
    }
  };
}

// Run tests
testUnifiedWorkflow().catch(console.error);