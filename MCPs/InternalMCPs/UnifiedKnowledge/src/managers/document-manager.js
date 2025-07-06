import crypto from 'crypto';

/**
 * Document Manager - Handles document versioning with Active-Archive pattern
 * Active Layer: Redis (Hashes, Streams)
 * Archive Layer: PostgreSQL (via postgresql-manager)
 * 
 * Redis Data Model:
 * - doc:{doc_id} (Hash) - Master document metadata
 * - doc:revisions:{doc_id} (Stream) - Revision log  
 * - revision:{revision_id} (Hash) - Revision content
 */
export class DocumentManager {
  constructor(redisManager, postgresManager) {
    this.redis = redisManager;
    this.postgres = postgresManager;
  }

  /**
   * Create a new document with initial content
   * Returns: { success: boolean, document_id: string, revision_id: string }
   */
  async createDocument(title, content, author, metadata = {}) {
    const documentId = crypto.randomUUID();
    const revisionId = crypto.randomUUID();
    const timestamp = Date.now();
    
    try {
      // Start Redis transaction for atomicity
      const pipeline = this.redis.client.multi();
      
      // 1. Create document master key
      pipeline.hset(`doc:${documentId}`, {
        latest_revision_id: revisionId,
        title: title,
        status: 'active',
        active_revision_count: 1,
        created_at: timestamp,
        updated_at: timestamp,
        created_by: author || 'unknown',
        metadata: JSON.stringify(metadata)
      });
      
      // 2. Add first revision to stream
      pipeline.xadd(`doc:revisions:${documentId}`, '*', 
        'revision_id', revisionId,
        'timestamp', timestamp,
        'author', author || 'unknown',
        'content_preview', content.substring(0, 200),
        'version_number', 1,
        'notes', 'Initial document creation'
      );
      
      // 3. Store revision content
      pipeline.hset(`revision:${revisionId}`, {
        content: content,
        parent_doc_id: documentId,
        author: author || 'unknown',
        version_number: 1,
        created_at: timestamp,
        notes: 'Initial document creation'
      });
      
      // Execute transaction
      await pipeline.exec();
      
      console.log(`[DocumentManager] Created document ${documentId} with revision ${revisionId}`);
      
      return {
        success: true,
        document_id: documentId,
        revision_id: revisionId,
        version_number: 1
      };
      
    } catch (error) {
      console.error('[DocumentManager] Failed to create document:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Update a document with new content (creates new revision)
   * Returns: { success: boolean, revision_id: string, version_number: number }
   */
  async updateDocument(documentId, content, author, notes = '') {
    try {
      // Check if document exists and get current info
      const docInfo = await this.redis.client.hgetall(`doc:${documentId}`);
      if (!docInfo || Object.keys(docInfo).length === 0) {
        return {
          success: false,
          error: 'Document not found'
        };
      }

      // Get current revision count to determine next version number
      const revisionCount = await this.redis.client.xlen(`doc:revisions:${documentId}`);
      const nextVersion = revisionCount + 1;
      
      const revisionId = crypto.randomUUID();
      const timestamp = Date.now();
      
      // Start Redis transaction
      const pipeline = this.redis.client.multi();
      
      // 1. Update document master key
      pipeline.hset(`doc:${documentId}`, {
        latest_revision_id: revisionId,
        updated_at: timestamp,
        active_revision_count: nextVersion
      });
      
      // 2. Add revision to stream
      pipeline.xadd(`doc:revisions:${documentId}`, '*',
        'revision_id', revisionId,
        'timestamp', timestamp,
        'author', author || 'unknown',
        'content_preview', content.substring(0, 200),
        'version_number', nextVersion,
        'notes', notes || `Update #${nextVersion}`
      );
      
      // 3. Store revision content
      pipeline.hset(`revision:${revisionId}`, {
        content: content,
        parent_doc_id: documentId,
        author: author || 'unknown',
        version_number: nextVersion,
        created_at: timestamp,
        notes: notes || `Update #${nextVersion}`
      });
      
      // Execute transaction
      await pipeline.exec();
      
      console.log(`[DocumentManager] Updated document ${documentId} with revision ${revisionId} (v${nextVersion})`);
      
      return {
        success: true,
        revision_id: revisionId,
        version_number: nextVersion
      };
      
    } catch (error) {
      console.error('[DocumentManager] Failed to update document:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Get a document (latest version by default, or specific revision)
   * Returns: { success: boolean, document: object }
   */
  async getDocument(documentId, revisionId = null) {
    try {
      // Get document master info
      const docInfo = await this.redis.client.hgetall(`doc:${documentId}`);
      if (!docInfo || Object.keys(docInfo).length === 0) {
        return {
          success: false,
          error: 'Document not found'
        };
      }

      // Determine which revision to fetch
      const targetRevisionId = revisionId || docInfo.latest_revision_id;
      
      // Get revision content
      const revisionContent = await this.redis.client.hgetall(`revision:${targetRevisionId}`);
      if (!revisionContent || Object.keys(revisionContent).length === 0) {
        // TODO: In Phase 4, check PostgreSQL archive if not found in Redis
        return {
          success: false,
          error: 'Revision not found in active storage'
        };
      }

      // Combine document and revision info
      const document = {
        document_id: documentId,
        title: docInfo.title,
        status: docInfo.status,
        created_by: docInfo.created_by,
        created_at: parseInt(docInfo.created_at),
        updated_at: parseInt(docInfo.updated_at),
        metadata: JSON.parse(docInfo.metadata || '{}'),
        
        // Current revision info
        revision_id: targetRevisionId,
        content: revisionContent.content,
        author: revisionContent.author,
        version_number: parseInt(revisionContent.version_number),
        revision_created_at: parseInt(revisionContent.created_at),
        notes: revisionContent.notes,
        
        // Active storage stats
        active_revision_count: parseInt(docInfo.active_revision_count)
      };

      return {
        success: true,
        document: document
      };
      
    } catch (error) {
      console.error('[DocumentManager] Failed to get document:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Get revision history for a document (active revisions from Redis)
   * Returns: { success: boolean, revisions: array }
   */
  async getDocumentHistory(documentId) {
    try {
      // Check if document exists
      const docExists = await this.redis.client.exists(`doc:${documentId}`);
      if (!docExists) {
        return {
          success: false,
          error: 'Document not found'
        };
      }

      // Get all revisions from stream (most recent first)
      const revisionStream = await this.redis.client.xrevrange(`doc:revisions:${documentId}`, '+', '-');
      
      const revisions = revisionStream.map(([streamId, fields]) => {
        // Convert fields array to object
        const revision = {};
        for (let i = 0; i < fields.length; i += 2) {
          revision[fields[i]] = fields[i + 1];
        }
        
        return {
          stream_id: streamId,
          revision_id: revision.revision_id,
          timestamp: parseInt(revision.timestamp),
          author: revision.author,
          version_number: parseInt(revision.version_number),
          content_preview: revision.content_preview,
          notes: revision.notes
        };
      });

      return {
        success: true,
        revisions: revisions,
        total_active_revisions: revisions.length
      };
      
    } catch (error) {
      console.error('[DocumentManager] Failed to get document history:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Get document list (active documents)
   * Returns: { success: boolean, documents: array }
   */
  async listDocuments(limit = 50, offset = 0) {
    try {
      // Scan for document keys
      const pattern = 'doc:*';
      const excludePattern = 'doc:revisions:*'; // Exclude revision streams
      
      let cursor = '0';
      let allKeys = [];
      
      do {
        const result = await this.redis.client.scan(cursor, 'MATCH', pattern, 'COUNT', 100);
        cursor = result[0];
        const keys = result[1].filter(key => !key.includes('revisions:'));
        allKeys.push(...keys);
      } while (cursor !== '0');
      
      // Sort keys and apply pagination
      allKeys.sort();
      const paginatedKeys = allKeys.slice(offset, offset + limit);
      
      // Get document info for each key
      const documents = [];
      for (const key of paginatedKeys) {
        const docInfo = await this.redis.client.hgetall(key);
        if (docInfo && Object.keys(docInfo).length > 0) {
          const documentId = key.replace('doc:', '');
          documents.push({
            document_id: documentId,
            title: docInfo.title,
            status: docInfo.status,
            created_by: docInfo.created_by,
            created_at: parseInt(docInfo.created_at),
            updated_at: parseInt(docInfo.updated_at),
            active_revision_count: parseInt(docInfo.active_revision_count),
            latest_revision_id: docInfo.latest_revision_id
          });
        }
      }
      
      return {
        success: true,
        documents: documents,
        total_found: allKeys.length,
        limit: limit,
        offset: offset
      };
      
    } catch (error) {
      console.error('[DocumentManager] Failed to list documents:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }
}