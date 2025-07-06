import { z } from 'zod';
import ResponseHandler from '../shared/response-handler.js';

// Validation schemas for document operations
const createDocumentSchema = z.object({
  action: z.literal('create'),
  title: z.string().min(1).max(500),
  content: z.string(),
  author: z.string().optional(),
  metadata: z.record(z.any()).optional()
});

const updateDocumentSchema = z.object({
  action: z.literal('update'),
  doc_id: z.string().uuid(),
  content: z.string(),
  author: z.string().optional(),
  notes: z.string().optional()
});

const getDocumentSchema = z.object({
  action: z.literal('get'),
  doc_id: z.string().uuid(),
  revision_id: z.string().uuid().optional()
});

const historyDocumentSchema = z.object({
  action: z.literal('history'),
  doc_id: z.string().uuid()
});

const listDocumentsSchema = z.object({
  action: z.literal('list'),
  limit: z.number().int().min(1).max(100).optional().default(50),
  offset: z.number().int().min(0).optional().default(0)
});

const documentSchema = z.discriminatedUnion('action', [
  createDocumentSchema,
  updateDocumentSchema,
  getDocumentSchema,
  historyDocumentSchema,
  listDocumentsSchema
]);

/**
 * Document tool - handles document versioning operations
 * Supports: create, update, get, history, list
 */
export async function handleDocumentTool(args, { documentManager }) {
  try {
    // Validate input
    const validatedArgs = documentSchema.parse(args);
    
    switch (validatedArgs.action) {
      case 'create':
        return await handleCreateDocument(validatedArgs, documentManager);
      
      case 'update':
        return await handleUpdateDocument(validatedArgs, documentManager);
      
      case 'get':
        return await handleGetDocument(validatedArgs, documentManager);
      
      case 'history':
        return await handleDocumentHistory(validatedArgs, documentManager);
      
      case 'list':
        return await handleListDocuments(validatedArgs, documentManager);
      
      default:
        return ResponseHandler.error('Unknown document action', 'INVALID_ACTION');
    }
    
  } catch (error) {
    if (error.name === 'ZodError') {
      return ResponseHandler.validationError(error);
    }
    
    console.error('[DocumentTool] Unexpected error:', error);
    return ResponseHandler.error('Internal server error', 'INTERNAL_ERROR');
  }
}

/**
 * Handle document creation
 */
async function handleCreateDocument(args, documentManager) {
  try {
    const result = await documentManager.createDocument(
      args.title,
      args.content,
      args.author,
      args.metadata
    );
    
    if (result.success) {
      return ResponseHandler.success('Document created successfully', {
        document_id: result.document_id,
        revision_id: result.revision_id,
        version_number: result.version_number,
        title: args.title,
        created_by: args.author || 'unknown'
      });
    } else {
      return ResponseHandler.error(`Failed to create document: ${result.error}`, 'CREATE_FAILED');
    }
    
  } catch (error) {
    console.error('[DocumentTool] Create error:', error);
    return ResponseHandler.error('Failed to create document', 'CREATE_ERROR');
  }
}

/**
 * Handle document update
 */
async function handleUpdateDocument(args, documentManager) {
  try {
    const result = await documentManager.updateDocument(
      args.doc_id,
      args.content,
      args.author,
      args.notes
    );
    
    if (result.success) {
      return ResponseHandler.success('Document updated successfully', {
        document_id: args.doc_id,
        revision_id: result.revision_id,
        version_number: result.version_number,
        updated_by: args.author || 'unknown'
      });
    } else {
      return ResponseHandler.error(`Failed to update document: ${result.error}`, 'UPDATE_FAILED');
    }
    
  } catch (error) {
    console.error('[DocumentTool] Update error:', error);
    return ResponseHandler.error('Failed to update document', 'UPDATE_ERROR');
  }
}

/**
 * Handle document retrieval
 */
async function handleGetDocument(args, documentManager) {
  try {
    const result = await documentManager.getDocument(args.doc_id, args.revision_id);
    
    if (result.success) {
      return ResponseHandler.success('Document retrieved successfully', {
        document: result.document
      });
    } else {
      return ResponseHandler.error(`Failed to get document: ${result.error}`, 'GET_FAILED');
    }
    
  } catch (error) {
    console.error('[DocumentTool] Get error:', error);
    return ResponseHandler.error('Failed to retrieve document', 'GET_ERROR');
  }
}

/**
 * Handle document history retrieval
 */
async function handleDocumentHistory(args, documentManager) {
  try {
    const result = await documentManager.getDocumentHistory(args.doc_id);
    
    if (result.success) {
      return ResponseHandler.success('Document history retrieved successfully', {
        document_id: args.doc_id,
        revisions: result.revisions,
        total_active_revisions: result.total_active_revisions
      });
    } else {
      return ResponseHandler.error(`Failed to get document history: ${result.error}`, 'HISTORY_FAILED');
    }
    
  } catch (error) {
    console.error('[DocumentTool] History error:', error);
    return ResponseHandler.error('Failed to retrieve document history', 'HISTORY_ERROR');
  }
}

/**
 * Handle document listing
 */
async function handleListDocuments(args, documentManager) {
  try {
    const result = await documentManager.listDocuments(args.limit, args.offset);
    
    if (result.success) {
      return ResponseHandler.success('Documents listed successfully', {
        documents: result.documents,
        total_found: result.total_found,
        limit: result.limit,
        offset: result.offset
      });
    } else {
      return ResponseHandler.error(`Failed to list documents: ${result.error}`, 'LIST_FAILED');
    }
    
  } catch (error) {
    console.error('[DocumentTool] List error:', error);
    return ResponseHandler.error('Failed to list documents', 'LIST_ERROR');
  }
}