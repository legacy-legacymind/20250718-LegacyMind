// src/managers/doc-manager.js
import { logger } from '../utils/logger.js';

export class DocManager {
  constructor(redisManager, dbManager, qdrantManager) {
    this.redis = redisManager;
    this.db = dbManager;
    this.qdrant = qdrantManager;
    this.activeDocsKey = 'docs:active';
    this.archivedDocsKey = 'docs:archived';
    this.docVersionsKey = 'docs:versions';
    this.inactiveStatuses = ['ARCHIVED', 'DEPRECATED', 'SUPERSEDED'];
  }

  generateDocId() {
    const timestamp = new Date().toISOString();
    const randomId = Math.random().toString(36).substring(2, 8);
    return `DOC-${timestamp.split('T')[0].replace(/-/g, '')}-${randomId.toUpperCase()}`;
  }

  parseVersion(version) {
    const parts = version.split('.').map(Number);
    return {
      major: parts[0] || 1,
      minor: parts[1] || 0,
      patch: parts[2] || 0
    };
  }

  incrementVersion(currentVersion, versionType = 'patch') {
    const { major, minor, patch } = this.parseVersion(currentVersion);
    
    switch (versionType) {
      case 'major':
        return `${major + 1}.0.0`;
      case 'minor':
        return `${major}.${minor + 1}.0`;
      case 'patch':
      default:
        return `${major}.${minor}.${patch + 1}`;
    }
  }

  async create(data) {
    const {
      title,
      author,
      category,
      content = '',
      doc_type = 'GENERAL',
      version = '1.0.0',
      status = 'ACTIVE',
      valid_from = new Date().toISOString(),
      valid_until = null,
      parent_doc_id = null,
      references = [],  // Accept 'references' from input
      doc_references = references,  // Map to doc_references
      tags = [],
      metadata = {},
      review_date = null,
      approval_status = 'DRAFT'
    } = data;

    if (!title || !author || !category) {
      throw new Error('Missing required fields: title, author, category');
    }

    const docId = this.generateDocId();
    const timestamp = new Date().toISOString();

    const docData = {
      doc_id: docId,
      title,
      content,
      category,
      doc_type,
      version,
      status,
      author,
      valid_from,
      valid_until,
      parent_doc_id,
      doc_references: JSON.stringify(doc_references),
      tags: JSON.stringify(tags),
      metadata: JSON.stringify(metadata),
      created_at: timestamp,
      updated_at: timestamp,
      review_date,
      approval_status,
      approved_by: null,
      approved_at: null
    };

    const transactionId = await this.db.beginTransaction();

    try {
      // 1. Save to PostgreSQL within transaction
      const result = await this.db.insertWithTransaction('system_docs', docData, transactionId);
      
      // 2. Cache in Redis
      const redisKey = `doc:${docId}`;
      await this.redis.hSet(redisKey, docData);
      await this.redis.client.sAdd(this.activeDocsKey, docId);
      
      // Track version history
      const versionKey = `doc:versions:${docId}`;
      await this.redis.client.lPush(versionKey, JSON.stringify({
        version,
        created_at: timestamp,
        author
      }));
      
      // Set TTL for Redis cache (30 days for active docs)
      await this.redis.client.expire(redisKey, 2592000);
      await this.redis.client.expire(versionKey, 2592000);

      // 3. Index in Qdrant for vector search
      await this.indexDocInQdrant(result);

      // Commit transaction
      await this.db.commitTransaction(transactionId);

      logger.info(`Document created: ${docId}`);
      return {
        success: true,
        doc_id: docId,
        data: result
      };
    } catch (error) {
      // Rollback database transaction
      await this.db.rollbackTransaction(transactionId);
      
      // Clean up Redis if possible (best effort)
      try {
        const redisKey = `doc:${docId}`;
        const versionKey = `doc:versions:${docId}`;
        await this.redis.client.del(redisKey);
        await this.redis.client.del(versionKey);
        await this.redis.client.sRem(this.activeDocsKey, docId);
      } catch (cleanupError) {
        logger.warn(`Failed to cleanup Redis for document ${docId}:`, cleanupError);
      }

      logger.error(`Failed to create document: ${error.message}`);
      throw error;
    }
  }

  async update(data) {
    const { doc_id, increment_version = false, version_type = 'patch', ...updateData } = data;

    if (!doc_id) {
      throw new Error('doc_id is required for update');
    }

    try {
      // Get current document
      const currentDoc = await this.db.query(
        'SELECT * FROM system_docs WHERE doc_id = $1',
        [doc_id]
      );

      if (currentDoc.rows.length === 0) {
        throw new Error(`Document not found: ${doc_id}`);
      }

      const current = currentDoc.rows[0];

      // Handle version increment if requested
      if (increment_version) {
        updateData.version = this.incrementVersion(current.version, version_type);
        
        // Track version change
        const versionKey = `doc:versions:${doc_id}`;
        await this.redis.client.lPush(versionKey, JSON.stringify({
          version: updateData.version,
          created_at: new Date().toISOString(),
          author: updateData.author || current.author
        }));
      }

      // Update PostgreSQL
      const columns = Object.keys(updateData);
      const values = Object.values(updateData);
      const setClause = columns.map((col, i) => `${col} = $${i + 2}`).join(', ');
      
      // Handle JSON fields
      const jsonFields = ['doc_references', 'tags', 'metadata'];
      values.forEach((value, index) => {
        if (jsonFields.includes(columns[index]) && typeof value !== 'string') {
          values[index] = JSON.stringify(value);
        }
      });

      const sql = `UPDATE system_docs SET ${setClause}, updated_at = CURRENT_TIMESTAMP WHERE doc_id = $1 RETURNING *`;
      const result = await this.db.query(sql, [doc_id, ...values]);

      const updatedDoc = result.rows[0];

      // Update Redis cache
      const redisKey = `doc:${doc_id}`;
      await this.redis.hSet(redisKey, updatedDoc);

      // Update Redis sets based on status
      if (this.inactiveStatuses.includes(updatedDoc.status)) {
        await this.redis.client.sRem(this.activeDocsKey, doc_id);
        await this.redis.client.sAdd(this.archivedDocsKey, doc_id);
      } else {
        await this.redis.client.sAdd(this.activeDocsKey, doc_id);
        await this.redis.client.sRem(this.archivedDocsKey, doc_id);
      }

      // Update Qdrant index
      await this.indexDocInQdrant(updatedDoc);

      logger.info(`Document updated: ${doc_id}`);
      return {
        success: true,
        doc_id,
        data: updatedDoc
      };
    } catch (error) {
      logger.error(`Failed to update document: ${error.message}`);
      throw error;
    }
  }

  async query(data) {
    const { 
      doc_id,
      category,
      status,
      author,
      doc_type,
      approval_status,
      valid_at,
      parent_doc_id,
      search_term,
      limit = 50,
      offset = 0,
      sort_by = 'created_at',
      sort_order = 'DESC'
    } = data;

    try {
      let sql = 'SELECT * FROM system_docs WHERE 1=1';
      const params = [];
      let paramCount = 0;

      if (doc_id) {
        sql += ` AND doc_id = $${++paramCount}`;
        params.push(doc_id);
      }

      if (category) {
        sql += ` AND category = $${++paramCount}`;
        params.push(category);
      }

      if (status) {
        sql += ` AND status = $${++paramCount}`;
        params.push(status);
      }

      if (author) {
        sql += ` AND author = $${++paramCount}`;
        params.push(author);
      }

      if (doc_type) {
        sql += ` AND doc_type = $${++paramCount}`;
        params.push(doc_type);
      }

      if (approval_status) {
        sql += ` AND approval_status = $${++paramCount}`;
        params.push(approval_status);
      }

      if (parent_doc_id) {
        sql += ` AND parent_doc_id = $${++paramCount}`;
        params.push(parent_doc_id);
      }

      if (valid_at) {
        sql += ` AND valid_from <= $${++paramCount} AND (valid_until IS NULL OR valid_until >= $${paramCount})`;
        params.push(valid_at);
      }

      if (search_term) {
        sql += ` AND (title ILIKE $${++paramCount} OR content ILIKE $${paramCount})`;
        params.push(`%${search_term}%`);
      }

      sql += ` ORDER BY ${sort_by} ${sort_order}`;
      sql += ` LIMIT $${++paramCount} OFFSET $${++paramCount}`;
      params.push(limit, offset);

      const result = await this.db.query(sql, params);
      
      // Parse JSON fields
      const docs = result.rows.map(row => ({
        ...row,
        doc_references: JSON.parse(row.doc_references || '[]'),
        tags: JSON.parse(row.tags || '[]'),
        metadata: JSON.parse(row.metadata || '{}')
      }));

      return {
        success: true,
        count: docs.length,
        total: result.rowCount,
        data: docs
      };
    } catch (error) {
      logger.error(`Failed to query documents: ${error.message}`);
      throw error;
    }
  }

  async delete(data) {
    const { doc_id } = data;

    if (!doc_id) {
      throw new Error('doc_id is required for deletion');
    }

    try {
      // Check for child documents
      const childDocs = await this.db.query(
        'SELECT COUNT(*) FROM system_docs WHERE parent_doc_id = $1',
        [doc_id]
      );

      if (parseInt(childDocs.rows[0].count) > 0) {
        throw new Error(`Cannot delete document ${doc_id}: it has child documents`);
      }

      // Delete from PostgreSQL
      const result = await this.db.query(
        'DELETE FROM system_docs WHERE doc_id = $1 RETURNING *',
        [doc_id]
      );

      if (result.rows.length === 0) {
        throw new Error(`Document not found: ${doc_id}`);
      }

      // Remove from Redis
      const redisKey = `doc:${doc_id}`;
      const versionKey = `doc:versions:${doc_id}`;
      await this.redis.client.del(redisKey);
      await this.redis.client.del(versionKey);
      await this.redis.client.sRem(this.activeDocsKey, doc_id);
      await this.redis.client.sRem(this.archivedDocsKey, doc_id);

      // Remove from Qdrant
      await this.removeDocFromQdrant(doc_id);

      logger.info(`Document deleted: ${doc_id}`);
      return {
        success: true,
        doc_id,
        message: `Document ${doc_id} deleted successfully`
      };
    } catch (error) {
      logger.error(`Failed to delete document: ${error.message}`);
      throw error;
    }
  }

  async addReference(data) {
    const { doc_id, reference } = data;

    if (!doc_id || !reference) {
      throw new Error('doc_id and reference are required');
    }

    // Validate reference format
    if (!reference.type || !reference.id) {
      throw new Error('Reference must have type and id fields');
    }

    const transactionId = await this.db.beginTransaction();

    try {
      // Get current document within transaction
      const result = await this.db.queryWithTransaction(
        'SELECT doc_references FROM system_docs WHERE doc_id = $1',
        [doc_id],
        transactionId
      );

      if (result.rows.length === 0) {
        throw new Error(`Document not found: ${doc_id}`);
      }

      const currentRefs = JSON.parse(result.rows[0].doc_references || '[]');
      
      // Check if reference already exists
      const exists = currentRefs.some(ref => 
        ref.type === reference.type && ref.id === reference.id
      );

      if (exists) {
        await this.db.commitTransaction(transactionId);
        return {
          success: true,
          message: `Reference already exists in document ${doc_id}`
        };
      }

      // Add timestamp to reference
      reference.added_at = new Date().toISOString();
      currentRefs.push(reference);

      // Update document within transaction
      const updateSql = 'UPDATE system_docs SET doc_references = $1, updated_at = CURRENT_TIMESTAMP WHERE doc_id = $2 RETURNING *';
      const updateResult = await this.db.queryWithTransaction(
        updateSql,
        [JSON.stringify(currentRefs), doc_id],
        transactionId
      );

      const updatedDoc = updateResult.rows[0];

      // Update Redis cache
      const redisKey = `doc:${doc_id}`;
      await this.redis.hSet(redisKey, updatedDoc);

      // Update Qdrant index
      await this.indexDocInQdrant(updatedDoc);

      // Commit transaction
      await this.db.commitTransaction(transactionId);

      logger.info(`Reference added to document ${doc_id}`);
      return {
        success: true,
        doc_id,
        data: updatedDoc
      };
    } catch (error) {
      await this.db.rollbackTransaction(transactionId);
      logger.error(`Failed to add reference: ${error.message}`);
      throw error;
    }
  }

  async removeReference(data) {
    const { doc_id, reference_type, reference_id } = data;

    if (!doc_id || !reference_type || !reference_id) {
      throw new Error('doc_id, reference_type, and reference_id are required');
    }

    const transactionId = await this.db.beginTransaction();

    try {
      // Get current document within transaction
      const result = await this.db.queryWithTransaction(
        'SELECT doc_references FROM system_docs WHERE doc_id = $1',
        [doc_id],
        transactionId
      );

      if (result.rows.length === 0) {
        throw new Error(`Document not found: ${doc_id}`);
      }

      const currentRefs = JSON.parse(result.rows[0].doc_references || '[]');
      const updatedRefs = currentRefs.filter(ref => 
        !(ref.type === reference_type && ref.id === reference_id)
      );

      if (currentRefs.length === updatedRefs.length) {
        await this.db.commitTransaction(transactionId);
        return {
          success: true,
          message: `Reference not found in document ${doc_id}`
        };
      }

      // Update document within transaction
      const updateSql = 'UPDATE system_docs SET doc_references = $1, updated_at = CURRENT_TIMESTAMP WHERE doc_id = $2 RETURNING *';
      const updateResult = await this.db.queryWithTransaction(
        updateSql,
        [JSON.stringify(updatedRefs), doc_id],
        transactionId
      );

      const updatedDoc = updateResult.rows[0];

      // Update Redis cache
      const redisKey = `doc:${doc_id}`;
      await this.redis.hSet(redisKey, updatedDoc);

      // Update Qdrant index
      await this.indexDocInQdrant(updatedDoc);

      // Commit transaction
      await this.db.commitTransaction(transactionId);

      logger.info(`Reference removed from document ${doc_id}`);
      return {
        success: true,
        doc_id,
        data: updatedDoc
      };
    } catch (error) {
      await this.db.rollbackTransaction(transactionId);
      logger.error(`Failed to remove reference: ${error.message}`);
      throw error;
    }
  }

  async indexDocInQdrant(doc) {
    try {
      const payload = {
        doc_id: doc.doc_id,
        title: doc.title,
        category: doc.category,
        doc_type: doc.doc_type,
        status: doc.status,
        author: doc.author,
        version: doc.version,
        created_at: doc.created_at,
        updated_at: doc.updated_at
      };

      await this.qdrant.indexDocument(doc.doc_id, doc.title, doc.content, payload);
    } catch (error) {
      logger.error(`Failed to index document in Qdrant: ${error.message}`);
      // Non-critical error, don't throw
    }
  }

  async removeDocFromQdrant(docId) {
    try {
      await this.qdrant.deleteDocument(docId);
    } catch (error) {
      logger.error(`Failed to remove document from Qdrant: ${error.message}`);
      // Non-critical error, don't throw
    }
  }
}