// src/managers/stats-manager.js
import { logger } from '../utils/logger.js';
import { ErrorHandler, ValidationError, OperationError } from '../utils/error-handler.js';

export class StatsManager {
  constructor(redisManager, dbManager) {
    this.redis = redisManager;
    this.db = dbManager;
    this.cachePrefix = 'stats:';
    this.cacheExpiry = 3600; // 1 hour
  }

  /**
   * Get ticket statistics
   * @param {object} filters - Filter criteria
   * @returns {object} - Statistics data
   */
  async getTicketStats(filters = {}) {
    return ErrorHandler.wrapOperation(async () => {
      const {
        status,
        priority,
        type,
        category,
        assignee,
        reporter,
        startDate,
        endDate
      } = filters;

      try {
        // Generate cache key based on filters
        const cacheKey = this.generateCacheKey('ticket_stats', filters);
        
        // Try to get from cache
        const cachedStats = await this.redis.get(cacheKey);
        if (cachedStats) {
          logger.debug('Returning cached ticket statistics', { cacheKey });
          return {
            success: true,
            stats: JSON.parse(cachedStats),
            cached: true
          };
        }

        // Build query with filters
        let query = 'SELECT * FROM ticket_stats_mv WHERE 1=1';
        const params = [];

        if (status) {
          query += ' AND status = $' + (params.length + 1);
          params.push(status);
        }

        if (priority) {
          query += ' AND priority = $' + (params.length + 1);
          params.push(priority);
        }

        if (type) {
          query += ' AND type = $' + (params.length + 1);
          params.push(type);
        }

        if (category) {
          query += ' AND category = $' + (params.length + 1);
          params.push(category);
        }

        if (assignee) {
          query += ' AND assignee = $' + (params.length + 1);
          params.push(assignee);
        }

        if (reporter) {
          query += ' AND reporter = $' + (params.length + 1);
          params.push(reporter);
        }

        // Execute query
        const rawStats = await this.db.query(query, params);

        // Process and aggregate results
        const stats = this.processTicketStats(rawStats, filters);

        // Cache the results
        await this.redis.setex(cacheKey, this.cacheExpiry, JSON.stringify(stats));

        logger.info('Generated ticket statistics', {
          filterCount: Object.keys(filters).length,
          resultCount: rawStats.length
        });

        return {
          success: true,
          stats,
          cached: false
        };
      } catch (error) {
        logger.error('Failed to get ticket statistics', {
          error: error.message,
          filters
        });
        throw new OperationError(
          `Failed to get ticket statistics: ${error.message}`,
          'getTicketStats',
          { filters }
        );
      }
    }, 'getTicketStats', { filters })();
  }

  /**
   * Process raw ticket statistics into structured format
   * @param {array} rawStats - Raw statistics from database
   * @param {object} filters - Applied filters
   * @returns {object} - Processed statistics
   */
  processTicketStats(rawStats, filters) {
    const stats = {
      summary: {
        total_tickets: 0,
        total_completed: 0,
        total_active: 0,
        total_estimated_hours: 0,
        total_logged_hours: 0,
        completion_rate: 0,
        average_lifecycle_hours: 0
      },
      breakdowns: {
        by_status: {},
        by_priority: {},
        by_type: {},
        by_category: {},
        by_assignee: {},
        by_reporter: {}
      },
      time_analysis: {
        estimation_accuracy: 0,
        average_estimated_hours: 0,
        average_logged_hours: 0,
        hours_variance: 0
      },
      trends: {
        oldest_ticket: null,
        newest_ticket: null,
        average_age_days: 0
      }
    };

    if (rawStats.length === 0) {
      return stats;
    }

    // Calculate summary statistics
    rawStats.forEach(row => {
      stats.summary.total_tickets += row.count;
      stats.summary.total_completed += row.completed_count;
      stats.summary.total_active += row.active_count;
      stats.summary.total_estimated_hours += row.avg_estimated_hours * row.count;
      stats.summary.total_logged_hours += row.total_logged_hours;

      // Build breakdowns
      this.addToBreakdown(stats.breakdowns.by_status, row.status, row);
      this.addToBreakdown(stats.breakdowns.by_priority, row.priority, row);
      this.addToBreakdown(stats.breakdowns.by_type, row.type, row);
      this.addToBreakdown(stats.breakdowns.by_category, row.category, row);
      this.addToBreakdown(stats.breakdowns.by_assignee, row.assignee, row);
      this.addToBreakdown(stats.breakdowns.by_reporter, row.reporter, row);

      // Track time trends
      if (!stats.trends.oldest_ticket || row.oldest_ticket < stats.trends.oldest_ticket) {
        stats.trends.oldest_ticket = row.oldest_ticket;
      }
      if (!stats.trends.newest_ticket || row.newest_ticket > stats.trends.newest_ticket) {
        stats.trends.newest_ticket = row.newest_ticket;
      }
    });

    // Calculate derived metrics
    stats.summary.completion_rate = stats.summary.total_tickets > 0 
      ? (stats.summary.total_completed / stats.summary.total_tickets) * 100 
      : 0;

    stats.summary.average_lifecycle_hours = rawStats.reduce((sum, row) => 
      sum + (row.lifecycle_hours * row.count), 0) / stats.summary.total_tickets;

    stats.time_analysis.average_estimated_hours = stats.summary.total_estimated_hours / stats.summary.total_tickets;
    stats.time_analysis.average_logged_hours = stats.summary.total_logged_hours / stats.summary.total_tickets;
    
    // Calculate estimation accuracy
    if (stats.summary.total_estimated_hours > 0) {
      stats.time_analysis.estimation_accuracy = 
        (stats.summary.total_logged_hours / stats.summary.total_estimated_hours) * 100;
    }

    stats.time_analysis.hours_variance = 
      Math.abs(stats.time_analysis.average_logged_hours - stats.time_analysis.average_estimated_hours);

    // Calculate average age
    if (stats.trends.oldest_ticket && stats.trends.newest_ticket) {
      const ageMs = new Date(stats.trends.newest_ticket) - new Date(stats.trends.oldest_ticket);
      stats.trends.average_age_days = ageMs / (1000 * 60 * 60 * 24);
    }

    return stats;
  }

  /**
   * Add row data to breakdown category
   * @param {object} breakdown - Breakdown object
   * @param {string} key - Category key
   * @param {object} row - Row data
   */
  addToBreakdown(breakdown, key, row) {
    if (!breakdown[key]) {
      breakdown[key] = {
        count: 0,
        completed: 0,
        active: 0,
        estimated_hours: 0,
        logged_hours: 0,
        completion_rate: 0
      };
    }

    breakdown[key].count += row.count;
    breakdown[key].completed += row.completed_count;
    breakdown[key].active += row.active_count;
    breakdown[key].estimated_hours += row.avg_estimated_hours * row.count;
    breakdown[key].logged_hours += row.total_logged_hours;
    breakdown[key].completion_rate = breakdown[key].count > 0 
      ? (breakdown[key].completed / breakdown[key].count) * 100 
      : 0;
  }

  /**
   * Get work log statistics
   * @param {object} filters - Filter criteria
   * @returns {object} - Work log statistics
   */
  async getWorkLogStats(filters = {}) {
    return ErrorHandler.wrapOperation(async () => {
      const {
        user_id,
        ticket_id,
        startDate,
        endDate,
        work_type,
        billable
      } = filters;

      try {
        const cacheKey = this.generateCacheKey('work_log_stats', filters);
        
        // Try cache first
        const cachedStats = await this.redis.get(cacheKey);
        if (cachedStats) {
          return {
            success: true,
            stats: JSON.parse(cachedStats),
            cached: true
          };
        }

        // Build query
        let query = `
          SELECT 
            COUNT(*) as total_logs,
            SUM(hours_worked) as total_hours,
            AVG(hours_worked) as avg_hours_per_log,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(DISTINCT ticket_id) as unique_tickets,
            COUNT(CASE WHEN billable = true THEN 1 END) as billable_logs,
            SUM(CASE WHEN billable = true THEN hours_worked ELSE 0 END) as billable_hours,
            work_type,
            DATE_TRUNC('day', work_date) as work_day
          FROM work_logs 
          WHERE 1=1
        `;
        
        const params = [];

        if (user_id) {
          query += ' AND user_id = $' + (params.length + 1);
          params.push(user_id);
        }

        if (ticket_id) {
          query += ' AND ticket_id = $' + (params.length + 1);
          params.push(ticket_id);
        }

        if (startDate) {
          query += ' AND work_date >= $' + (params.length + 1);
          params.push(startDate);
        }

        if (endDate) {
          query += ' AND work_date <= $' + (params.length + 1);
          params.push(endDate);
        }

        if (work_type) {
          query += ' AND work_type = $' + (params.length + 1);
          params.push(work_type);
        }

        if (billable !== undefined) {
          query += ' AND billable = $' + (params.length + 1);
          params.push(billable);
        }

        query += ' GROUP BY work_type, DATE_TRUNC(\'day\', work_date)';

        const rawStats = await this.db.query(query, params);

        // Process work log statistics
        const stats = this.processWorkLogStats(rawStats);

        // Cache results
        await this.redis.setex(cacheKey, this.cacheExpiry, JSON.stringify(stats));

        logger.info('Generated work log statistics', {
          filterCount: Object.keys(filters).length,
          resultCount: rawStats.length
        });

        return {
          success: true,
          stats,
          cached: false
        };
      } catch (error) {
        logger.error('Failed to get work log statistics', {
          error: error.message,
          filters
        });
        throw new OperationError(
          `Failed to get work log statistics: ${error.message}`,
          'getWorkLogStats',
          { filters }
        );
      }
    }, 'getWorkLogStats', { filters })();
  }

  /**
   * Process raw work log statistics
   * @param {array} rawStats - Raw statistics from database
   * @returns {object} - Processed statistics
   */
  processWorkLogStats(rawStats) {
    const stats = {
      summary: {
        total_logs: 0,
        total_hours: 0,
        total_billable_hours: 0,
        unique_users: 0,
        unique_tickets: 0,
        average_hours_per_log: 0,
        billable_percentage: 0
      },
      breakdowns: {
        by_work_type: {},
        by_day: {}
      }
    };

    if (rawStats.length === 0) {
      return stats;
    }

    const uniqueUsers = new Set();
    const uniqueTickets = new Set();

    rawStats.forEach(row => {
      stats.summary.total_logs += parseInt(row.total_logs);
      stats.summary.total_hours += parseFloat(row.total_hours);
      stats.summary.total_billable_hours += parseFloat(row.billable_hours);

      // Track unique users and tickets (this is approximate since we're working with aggregated data)
      uniqueUsers.add(row.user_id);
      uniqueTickets.add(row.ticket_id);

      // Build breakdowns
      if (!stats.breakdowns.by_work_type[row.work_type]) {
        stats.breakdowns.by_work_type[row.work_type] = {
          logs: 0,
          hours: 0,
          billable_hours: 0
        };
      }
      stats.breakdowns.by_work_type[row.work_type].logs += parseInt(row.total_logs);
      stats.breakdowns.by_work_type[row.work_type].hours += parseFloat(row.total_hours);
      stats.breakdowns.by_work_type[row.work_type].billable_hours += parseFloat(row.billable_hours);

      // Daily breakdown
      const day = row.work_day.toISOString().split('T')[0];
      if (!stats.breakdowns.by_day[day]) {
        stats.breakdowns.by_day[day] = {
          logs: 0,
          hours: 0,
          billable_hours: 0
        };
      }
      stats.breakdowns.by_day[day].logs += parseInt(row.total_logs);
      stats.breakdowns.by_day[day].hours += parseFloat(row.total_hours);
      stats.breakdowns.by_day[day].billable_hours += parseFloat(row.billable_hours);
    });

    // Calculate derived metrics
    stats.summary.unique_users = uniqueUsers.size;
    stats.summary.unique_tickets = uniqueTickets.size;
    stats.summary.average_hours_per_log = stats.summary.total_logs > 0 
      ? stats.summary.total_hours / stats.summary.total_logs 
      : 0;
    stats.summary.billable_percentage = stats.summary.total_hours > 0 
      ? (stats.summary.total_billable_hours / stats.summary.total_hours) * 100 
      : 0;

    return stats;
  }

  /**
   * Refresh materialized view
   * @returns {object} - Refresh result
   */
  async refreshStats() {
    return ErrorHandler.wrapOperation(async () => {
      try {
        await this.db.query('SELECT refresh_ticket_stats()');
        
        // Clear related caches
        await this.clearStatsCache();

        logger.info('Materialized view refreshed successfully');

        return {
          success: true,
          message: 'Statistics refreshed successfully'
        };
      } catch (error) {
        logger.error('Failed to refresh statistics', {
          error: error.message
        });
        throw new OperationError(
          `Failed to refresh statistics: ${error.message}`,
          'refreshStats'
        );
      }
    }, 'refreshStats')();
  }

  /**
   * Clear statistics cache
   * @returns {Promise} - Clear result
   */
  async clearStatsCache() {
    try {
      const pattern = `${this.cachePrefix}*`;
      const keys = await this.redis.client.keys(pattern);
      
      if (keys.length > 0) {
        await this.redis.client.del(...keys);
        logger.info('Statistics cache cleared', { keysCleared: keys.length });
      }
    } catch (error) {
      logger.warn('Failed to clear statistics cache', {
        error: error.message
      });
    }
  }

  /**
   * Generate cache key for statistics
   * @param {string} type - Statistics type
   * @param {object} filters - Filter criteria
   * @returns {string} - Cache key
   */
  generateCacheKey(type, filters) {
    const filterStr = JSON.stringify(filters, Object.keys(filters).sort());
    const hash = Buffer.from(filterStr).toString('base64').slice(0, 16);
    return `${this.cachePrefix}${type}:${hash}`;
  }
}