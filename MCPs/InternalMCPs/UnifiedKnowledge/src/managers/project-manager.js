// src/managers/project-manager.js
import { logger } from '../utils/logger.js';

export class ProjectManager {
  constructor(redisManager, dbManager, qdrantManager) {
    this.redis = redisManager;
    this.db = dbManager;
    this.qdrant = qdrantManager;
    this.activeProjectsKey = 'projects:active';
    this.archivedProjectsKey = 'projects:archived';
    this.completedStatuses = ['COMPLETED', 'CANCELLED', 'ARCHIVED'];
  }

  generateProjectId() {
    const timestamp = new Date().toISOString();
    const randomId = Math.random().toString(36).substring(2, 8);
    return `PROJ-${timestamp.split('T')[0].replace(/-/g, '')}-${randomId.toUpperCase()}`;
  }

  async create(data) {
    const {
      name,
      owner,
      description = null,
      category = 'GENERAL',
      priority = 'MEDIUM',
      status = 'ACTIVE',
      members = [],
      start_date = null,
      end_date = null,
      estimated_hours = 0,
      budget_allocated = null,
      milestones = [],
      tags = [],
      metadata = {}
    } = data;

    if (!name || !owner) {
      throw new Error('Missing required fields: name, owner');
    }

    const projectId = this.generateProjectId();
    const timestamp = new Date().toISOString();

    const projectData = {
      project_id: projectId,
      name,
      description,
      status,
      priority,
      category,
      owner,
      members: JSON.stringify(members),
      linked_tickets: JSON.stringify([]),
      metadata: JSON.stringify(metadata),
      created_at: timestamp,
      updated_at: timestamp,
      start_date,
      end_date,
      estimated_hours,
      actual_hours: 0,
      budget_allocated,
      budget_used: 0,
      milestones: JSON.stringify(milestones),
      tags: JSON.stringify(tags)
    };

    const transactionId = await this.db.beginTransaction();
    
    try {
      // 1. Save to PostgreSQL within transaction
      const result = await this.db.insertWithTransaction('projects', projectData, transactionId);
      
      // 2. Cache in Redis
      const redisKey = `project:${projectId}`;
      await this.redis.hSet(redisKey, projectData);
      await this.redis.client.sAdd(this.activeProjectsKey, projectId);
      
      // Set TTL for Redis cache (7 days for active projects)
      await this.redis.client.expire(redisKey, 604800);

      // 3. Index in Qdrant for vector search
      await this.indexProjectInQdrant(result);

      // If we get here, commit the transaction
      await this.db.commitTransaction(transactionId);

      logger.info(`Project created: ${projectId}`);
      return {
        success: true,
        project_id: projectId,
        data: result
      };
    } catch (error) {
      // Rollback database transaction
      await this.db.rollbackTransaction(transactionId);
      
      // Clean up Redis if possible (best effort)
      try {
        const redisKey = `project:${projectId}`;
        await this.redis.client.del(redisKey);
        await this.redis.client.sRem(this.activeProjectsKey, projectId);
      } catch (cleanupError) {
        logger.warn(`Failed to cleanup Redis for project ${projectId}:`, cleanupError);
      }

      logger.error(`Failed to create project: ${error.message}`);
      throw error;
    }
  }

  async update(data) {
    const { project_id, ...updateData } = data;

    if (!project_id) {
      throw new Error('project_id is required for update');
    }

    try {
      // Update PostgreSQL
      const columns = Object.keys(updateData);
      const values = Object.values(updateData);
      const setClause = columns.map((col, i) => `${col} = $${i + 2}`).join(', ');
      
      // Handle JSON fields
      const jsonFields = ['members', 'linked_tickets', 'metadata', 'milestones', 'tags'];
      values.forEach((value, index) => {
        if (jsonFields.includes(columns[index]) && typeof value !== 'string') {
          values[index] = JSON.stringify(value);
        }
      });

      const sql = `UPDATE projects SET ${setClause}, updated_at = CURRENT_TIMESTAMP WHERE project_id = $1 RETURNING *`;
      const result = await this.db.query(sql, [project_id, ...values]);

      if (result.rows.length === 0) {
        throw new Error(`Project not found: ${project_id}`);
      }

      const updatedProject = result.rows[0];

      // Update Redis cache
      const redisKey = `project:${project_id}`;
      await this.redis.hSet(redisKey, updatedProject);

      // Update Redis sets based on status
      if (this.completedStatuses.includes(updatedProject.status)) {
        await this.redis.client.sRem(this.activeProjectsKey, project_id);
        await this.redis.client.sAdd(this.archivedProjectsKey, project_id);
      } else {
        await this.redis.client.sAdd(this.activeProjectsKey, project_id);
        await this.redis.client.sRem(this.archivedProjectsKey, project_id);
      }

      // Update Qdrant index
      await this.indexProjectInQdrant(updatedProject);

      logger.info(`Project updated: ${project_id}`);
      return {
        success: true,
        project_id,
        data: updatedProject
      };
    } catch (error) {
      logger.error(`Failed to update project: ${error.message}`);
      throw error;
    }
  }

  async query(data) {
    const { 
      project_id,
      status,
      owner,
      category,
      member,
      limit = 50,
      offset = 0,
      sort_by = 'created_at',
      sort_order = 'DESC'
    } = data;

    try {
      let sql = 'SELECT * FROM projects WHERE 1=1';
      const params = [];
      let paramCount = 0;

      if (project_id) {
        sql += ` AND project_id = $${++paramCount}`;
        params.push(project_id);
      }

      if (status) {
        sql += ` AND status = $${++paramCount}`;
        params.push(status);
      }

      if (owner) {
        sql += ` AND owner = $${++paramCount}`;
        params.push(owner);
      }

      if (category) {
        sql += ` AND category = $${++paramCount}`;
        params.push(category);
      }

      if (member) {
        sql += ` AND members::jsonb @> $${++paramCount}`;
        params.push(JSON.stringify([member]));
      }

      sql += ` ORDER BY ${sort_by} ${sort_order}`;
      sql += ` LIMIT $${++paramCount} OFFSET $${++paramCount}`;
      params.push(limit, offset);

      const result = await this.db.query(sql, params);
      
      // Parse JSON fields
      const projects = result.rows.map(row => ({
        ...row,
        members: JSON.parse(row.members || '[]'),
        linked_tickets: JSON.parse(row.linked_tickets || '[]'),
        metadata: JSON.parse(row.metadata || '{}'),
        milestones: JSON.parse(row.milestones || '[]'),
        tags: JSON.parse(row.tags || '[]')
      }));

      return {
        success: true,
        count: projects.length,
        total: result.rowCount,
        data: projects
      };
    } catch (error) {
      logger.error(`Failed to query projects: ${error.message}`);
      throw error;
    }
  }

  async delete(data) {
    const { project_id } = data;

    if (!project_id) {
      throw new Error('project_id is required for deletion');
    }

    try {
      // Delete from PostgreSQL
      const result = await this.db.query(
        'DELETE FROM projects WHERE project_id = $1 RETURNING *',
        [project_id]
      );

      if (result.rows.length === 0) {
        throw new Error(`Project not found: ${project_id}`);
      }

      // Remove from Redis
      const redisKey = `project:${project_id}`;
      await this.redis.client.del(redisKey);
      await this.redis.client.sRem(this.activeProjectsKey, project_id);
      await this.redis.client.sRem(this.archivedProjectsKey, project_id);

      // Remove from Qdrant
      await this.removeProjectFromQdrant(project_id);

      logger.info(`Project deleted: ${project_id}`);
      return {
        success: true,
        project_id,
        message: `Project ${project_id} deleted successfully`
      };
    } catch (error) {
      logger.error(`Failed to delete project: ${error.message}`);
      throw error;
    }
  }

  async addMember(data) {
    const { project_id, member } = data;

    if (!project_id || !member) {
      throw new Error('project_id and member are required');
    }

    const transactionId = await this.db.beginTransaction();

    try {
      // Get current project within transaction
      const result = await this.db.queryWithTransaction(
        'SELECT members FROM projects WHERE project_id = $1',
        [project_id],
        transactionId
      );

      if (result.rows.length === 0) {
        throw new Error(`Project not found: ${project_id}`);
      }

      const currentMembers = JSON.parse(result.rows[0].members || '[]');
      
      if (currentMembers.includes(member)) {
        await this.db.commitTransaction(transactionId);
        return {
          success: true,
          message: `${member} is already a member of project ${project_id}`
        };
      }

      currentMembers.push(member);

      // Update project within transaction
      const updateSql = 'UPDATE projects SET members = $1, updated_at = CURRENT_TIMESTAMP WHERE project_id = $2 RETURNING *';
      const updateResult = await this.db.queryWithTransaction(
        updateSql,
        [JSON.stringify(currentMembers), project_id],
        transactionId
      );

      const updatedProject = updateResult.rows[0];

      // Update Redis cache
      const redisKey = `project:${project_id}`;
      await this.redis.hSet(redisKey, updatedProject);

      // Update Qdrant index
      await this.indexProjectInQdrant(updatedProject);

      // Commit transaction
      await this.db.commitTransaction(transactionId);

      logger.info(`Member ${member} added to project ${project_id}`);
      return {
        success: true,
        project_id,
        data: updatedProject
      };
    } catch (error) {
      await this.db.rollbackTransaction(transactionId);
      logger.error(`Failed to add member: ${error.message}`);
      throw error;
    }
  }

  async removeMember(data) {
    const { project_id, member } = data;

    if (!project_id || !member) {
      throw new Error('project_id and member are required');
    }

    const transactionId = await this.db.beginTransaction();

    try {
      // Get current project within transaction
      const result = await this.db.queryWithTransaction(
        'SELECT members, owner FROM projects WHERE project_id = $1',
        [project_id],
        transactionId
      );

      if (result.rows.length === 0) {
        throw new Error(`Project not found: ${project_id}`);
      }

      const project = result.rows[0];
      
      if (project.owner === member) {
        throw new Error('Cannot remove the project owner');
      }

      const currentMembers = JSON.parse(project.members || '[]');
      const updatedMembers = currentMembers.filter(m => m !== member);

      if (currentMembers.length === updatedMembers.length) {
        await this.db.commitTransaction(transactionId);
        return {
          success: true,
          message: `${member} is not a member of project ${project_id}`
        };
      }

      // Update project within transaction
      const updateSql = 'UPDATE projects SET members = $1, updated_at = CURRENT_TIMESTAMP WHERE project_id = $2 RETURNING *';
      const updateResult = await this.db.queryWithTransaction(
        updateSql,
        [JSON.stringify(updatedMembers), project_id],
        transactionId
      );

      const updatedProject = updateResult.rows[0];

      // Update Redis cache
      const redisKey = `project:${project_id}`;
      await this.redis.hSet(redisKey, updatedProject);

      // Update Qdrant index
      await this.indexProjectInQdrant(updatedProject);

      // Commit transaction
      await this.db.commitTransaction(transactionId);

      logger.info(`Member ${member} removed from project ${project_id}`);
      return {
        success: true,
        project_id,
        data: updatedProject
      };
    } catch (error) {
      await this.db.rollbackTransaction(transactionId);
      logger.error(`Failed to remove member: ${error.message}`);
      throw error;
    }
  }

  async linkTicket(data) {
    const { project_id, ticket_id } = data;

    if (!project_id || !ticket_id) {
      throw new Error('project_id and ticket_id are required');
    }

    const transactionId = await this.db.beginTransaction();

    try {
      // Get current project within transaction
      const result = await this.db.queryWithTransaction(
        'SELECT linked_tickets FROM projects WHERE project_id = $1',
        [project_id],
        transactionId
      );

      if (result.rows.length === 0) {
        throw new Error(`Project not found: ${project_id}`);
      }

      const linkedTicketsValue = result.rows[0].linked_tickets;
      const currentTickets = linkedTicketsValue ? JSON.parse(linkedTicketsValue) : [];
      
      if (currentTickets.includes(ticket_id)) {
        await this.db.commitTransaction(transactionId);
        return {
          success: true,
          message: `Ticket ${ticket_id} is already linked to project ${project_id}`
        };
      }

      currentTickets.push(ticket_id);

      // Update project within transaction
      const updateSql = 'UPDATE projects SET linked_tickets = $1, updated_at = CURRENT_TIMESTAMP WHERE project_id = $2 RETURNING *';
      const updateResult = await this.db.queryWithTransaction(
        updateSql,
        [JSON.stringify(currentTickets), project_id],
        transactionId
      );

      const updatedProject = updateResult.rows[0];

      // Update Redis cache
      const redisKey = `project:${project_id}`;
      await this.redis.hSet(redisKey, updatedProject);

      // Update Qdrant index
      await this.indexProjectInQdrant(updatedProject);

      // Commit transaction
      await this.db.commitTransaction(transactionId);

      logger.info(`Ticket ${ticket_id} linked to project ${project_id}`);
      return {
        success: true,
        project_id,
        data: updatedProject
      };
    } catch (error) {
      await this.db.rollbackTransaction(transactionId);
      logger.error(`Failed to link ticket: ${error.message}`);
      throw error;
    }
  }

  async unlinkTicket(data) {
    const { project_id, ticket_id } = data;

    if (!project_id || !ticket_id) {
      throw new Error('project_id and ticket_id are required');
    }

    const transactionId = await this.db.beginTransaction();

    try {
      // Get current project within transaction
      const result = await this.db.queryWithTransaction(
        'SELECT linked_tickets FROM projects WHERE project_id = $1',
        [project_id],
        transactionId
      );

      if (result.rows.length === 0) {
        throw new Error(`Project not found: ${project_id}`);
      }

      const currentTickets = JSON.parse(result.rows[0].linked_tickets || '[]');
      const updatedTickets = currentTickets.filter(t => t !== ticket_id);

      if (currentTickets.length === updatedTickets.length) {
        await this.db.commitTransaction(transactionId);
        return {
          success: true,
          message: `Ticket ${ticket_id} is not linked to project ${project_id}`
        };
      }

      // Update project within transaction
      const updateSql = 'UPDATE projects SET linked_tickets = $1, updated_at = CURRENT_TIMESTAMP WHERE project_id = $2 RETURNING *';
      const updateResult = await this.db.queryWithTransaction(
        updateSql,
        [JSON.stringify(updatedTickets), project_id],
        transactionId
      );

      const updatedProject = updateResult.rows[0];

      // Update Redis cache
      const redisKey = `project:${project_id}`;
      await this.redis.hSet(redisKey, updatedProject);

      // Update Qdrant index
      await this.indexProjectInQdrant(updatedProject);

      // Commit transaction
      await this.db.commitTransaction(transactionId);

      logger.info(`Ticket ${ticket_id} unlinked from project ${project_id}`);
      return {
        success: true,
        project_id,
        data: updatedProject
      };
    } catch (error) {
      await this.db.rollbackTransaction(transactionId);
      logger.error(`Failed to unlink ticket: ${error.message}`);
      throw error;
    }
  }

  async indexProjectInQdrant(project) {
    try {
      const payload = {
        project_id: project.project_id,
        name: project.name,
        description: project.description,
        category: project.category,
        status: project.status,
        owner: project.owner,
        created_at: project.created_at,
        updated_at: project.updated_at
      };

      await this.qdrant.indexProject(project.project_id, project.name, project.description, payload);
    } catch (error) {
      logger.error(`Failed to index project in Qdrant: ${error.message}`);
      // Non-critical error, don't throw
    }
  }

  async removeProjectFromQdrant(projectId) {
    try {
      await this.qdrant.deleteProject(projectId);
    } catch (error) {
      logger.error(`Failed to remove project from Qdrant: ${error.message}`);
      // Non-critical error, don't throw
    }
  }
}