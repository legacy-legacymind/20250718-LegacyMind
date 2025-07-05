import { Pool } from 'pg';

class PostgreSQLManager {
  constructor(connectionConfig) {
    this.pool = new Pool(connectionConfig);
    this.isConnected = false;
  }

  async connect() {
    try {
      // Test connection
      const client = await this.pool.connect();
      await client.query('SELECT 1');
      client.release();
      
      console.log('[PostgreSQL] Connected to database');
      this.isConnected = true;
      
      return true;
    } catch (error) {
      console.error('[PostgreSQL] Connection failed:', error);
      this.isConnected = false;
      throw error;
    }
  }

  async healthCheck() {
    try {
      await this.pool.query('SELECT 1');
      return { status: 'healthy', timestamp: new Date().toISOString() };
    } catch (error) {
      return { 
        status: 'unhealthy', 
        error: error.message, 
        timestamp: new Date().toISOString() 
      };
    }
  }

  async archiveTicket(ticketData) {
    const query = `
      INSERT INTO archived_tickets (
        id, title, description, status, priority, 
        assignee, reporter, created_at, updated_at, 
        resolved_at, labels, comments, metadata
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
      ON CONFLICT (id) DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        status = EXCLUDED.status,
        priority = EXCLUDED.priority,
        assignee = EXCLUDED.assignee,
        reporter = EXCLUDED.reporter,
        updated_at = EXCLUDED.updated_at,
        resolved_at = EXCLUDED.resolved_at,
        labels = EXCLUDED.labels,
        comments = EXCLUDED.comments,
        metadata = EXCLUDED.metadata
    `;

    const values = [
      ticketData.id,
      ticketData.title,
      ticketData.description,
      ticketData.status,
      ticketData.priority,
      ticketData.assignee,
      ticketData.reporter,
      ticketData.created_at,
      ticketData.updated_at,
      ticketData.resolved_at,
      ticketData.labels ? JSON.stringify(ticketData.labels) : null,
      ticketData.comments ? JSON.stringify(ticketData.comments) : null,
      ticketData.metadata ? JSON.stringify(ticketData.metadata) : null
    ];

    try {
      await this.pool.query(query, values);
      return { success: true };
    } catch (error) {
      throw new Error(`Failed to archive ticket: ${error.message}`);
    }
  }

  async searchArchivedTickets(searchCriteria = {}) {
    const conditions = [];
    const values = [];
    let paramCount = 0;

    // Build dynamic WHERE clause with parameterized queries
    if (searchCriteria.id) {
      conditions.push(`id = $${++paramCount}`);
      values.push(searchCriteria.id);
    }

    if (searchCriteria.status) {
      conditions.push(`status = $${++paramCount}`);
      values.push(searchCriteria.status);
    }

    if (searchCriteria.priority) {
      conditions.push(`priority = $${++paramCount}`);
      values.push(searchCriteria.priority);
    }

    if (searchCriteria.assignee) {
      conditions.push(`assignee = $${++paramCount}`);
      values.push(searchCriteria.assignee);
    }

    if (searchCriteria.reporter) {
      conditions.push(`reporter = $${++paramCount}`);
      values.push(searchCriteria.reporter);
    }

    if (searchCriteria.text) {
      // Search in title and description
      conditions.push(`(title ILIKE $${++paramCount} OR description ILIKE $${paramCount})`);
      values.push(`%${searchCriteria.text}%`);
    }

    if (searchCriteria.dateFrom) {
      conditions.push(`created_at >= $${++paramCount}`);
      values.push(searchCriteria.dateFrom);
    }

    if (searchCriteria.dateTo) {
      conditions.push(`created_at <= $${++paramCount}`);
      values.push(searchCriteria.dateTo);
    }

    if (searchCriteria.resolvedFrom) {
      conditions.push(`resolved_at >= $${++paramCount}`);
      values.push(searchCriteria.resolvedFrom);
    }

    if (searchCriteria.resolvedTo) {
      conditions.push(`resolved_at <= $${++paramCount}`);
      values.push(searchCriteria.resolvedTo);
    }

    if (searchCriteria.labels && searchCriteria.labels.length > 0) {
      // Search for tickets containing any of the specified labels
      const labelConditions = searchCriteria.labels.map(() => {
        return `labels::jsonb @> $${++paramCount}::jsonb`;
      });
      conditions.push(`(${labelConditions.join(' OR ')})`);
      searchCriteria.labels.forEach(label => {
        values.push(JSON.stringify([label]));
      });
    }

    // Build the final query
    let query = 'SELECT * FROM archived_tickets';
    if (conditions.length > 0) {
      query += ' WHERE ' + conditions.join(' AND ');
    }

    // Add sorting
    const sortField = searchCriteria.sortBy || 'created_at';
    const sortOrder = searchCriteria.sortOrder || 'DESC';
    query += ` ORDER BY ${sortField} ${sortOrder}`;

    // Add pagination
    if (searchCriteria.limit) {
      query += ` LIMIT $${++paramCount}`;
      values.push(searchCriteria.limit);
    }

    if (searchCriteria.offset) {
      query += ` OFFSET $${++paramCount}`;
      values.push(searchCriteria.offset);
    }

    try {
      const result = await this.pool.query(query, values);
      
      // Parse JSON fields
      const tickets = result.rows.map(row => ({
        ...row,
        labels: row.labels ? JSON.parse(row.labels) : [],
        comments: row.comments ? JSON.parse(row.comments) : [],
        metadata: row.metadata ? JSON.parse(row.metadata) : {}
      }));

      return tickets;
    } catch (error) {
      throw new Error(`Failed to search archived tickets: ${error.message}`);
    }
  }

  async disconnect() {
    if (this.pool) {
      await this.pool.end();
      this.isConnected = false;
      console.log('[PostgreSQL] Disconnected gracefully');
    }
  }
}

export { PostgreSQLManager };