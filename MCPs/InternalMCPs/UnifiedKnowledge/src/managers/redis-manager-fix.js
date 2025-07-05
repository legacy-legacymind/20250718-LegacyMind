// Additional method to add to redis-manager.js after searchTickets method

  // Search tickets where user is involved (as reporter OR assignee)
  async getTicketsByUser(username) {
    try {
      const usernameLower = username.toLowerCase();
      
      // Get tickets where user is assignee
      const assigneeKey = `index:assignee:${usernameLower}`;
      const assignedTicketIds = await this.client.sMembers(assigneeKey);
      
      // Get tickets where user is reporter
      const reporterKey = `index:reporter:${usernameLower}`;
      const reportedTicketIds = await this.client.sMembers(reporterKey);
      
      // Combine and deduplicate
      const allTicketIds = [...new Set([...assignedTicketIds, ...reportedTicketIds])];
      
      // Get full ticket data
      const tickets = [];
      for (const ticketId of allTicketIds) {
        const ticket = await this.getTicket(ticketId);
        if (ticket) {
          tickets.push(ticket);
        }
      }
      
      // Sort by creation date (newest first)
      tickets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      
      return tickets;
    } catch (error) {
      console.error(`[Redis] Failed to get tickets by user ${username}:`, error);
      throw new Error(`Failed to get tickets by user: ${error.message}`);
    }
  }

  // Enhanced search with involvement option
  async searchTicketsEnhanced(filters = {}) {
    try {
      // If 'involved' filter is specified, use the new method
      if (filters.involved) {
        return await this.getTicketsByUser(filters.involved);
      }
      
      // Otherwise use the existing search logic
      return await this.searchTickets(filters);
    } catch (error) {
      console.error('[Redis] Failed to search tickets (enhanced):', error);
      throw new Error(`Failed to search tickets: ${error.message}`);
    }
  }