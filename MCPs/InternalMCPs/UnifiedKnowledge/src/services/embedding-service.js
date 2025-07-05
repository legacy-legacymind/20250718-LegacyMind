import OpenAI from 'openai';

export class EmbeddingService {
  constructor() {
    this.openai = null;
    this.model = 'text-embedding-3-small';
    this.initialize();
  }

  initialize() {
    const apiKey = process.env.OPENAI_API_KEY;
    
    if (!apiKey) {
      throw new Error('OPENAI_API_KEY environment variable is required');
    }
    
    this.openai = new OpenAI({
      apiKey: apiKey
    });
    
    console.error('[Embedding] OpenAI embedding service initialized');
  }

  async generateEmbedding(text) {
    if (!text || typeof text !== 'string' || text.trim().length === 0) {
      throw new Error('Text is required for embedding generation');
    }

    try {
      const response = await this.openai.embeddings.create({
        model: this.model,
        input: text.trim(),
        encoding_format: 'float'
      });

      if (!response.data || response.data.length === 0) {
        throw new Error('No embedding data received from OpenAI');
      }

      return response.data[0].embedding;
    } catch (error) {
      console.error('[Embedding] Failed to generate embedding:', error);
      throw new Error(`Embedding generation failed: ${error.message}`);
    }
  }

  async generateTicketEmbedding(ticketData) {
    // Create a comprehensive text representation of the ticket
    const textParts = [
      `Ticket ID: ${ticketData.ticket_id}`,
      `Title: ${ticketData.title}`,
      `Type: ${ticketData.type}`,
      `Category: ${ticketData.category}`,
      `Priority: ${ticketData.priority}`,
      `Status: ${ticketData.status}`
    ];

    if (ticketData.system) {
      textParts.push(`System: ${ticketData.system}`);
    }

    if (ticketData.description) {
      textParts.push(`Description: ${ticketData.description}`);
    }

    if (ticketData.resolution) {
      textParts.push(`Resolution: ${ticketData.resolution}`);
    }

    if (ticketData.tags && ticketData.tags.length > 0) {
      textParts.push(`Tags: ${ticketData.tags.join(', ')}`);
    }

    if (ticketData.acceptance_criteria && ticketData.acceptance_criteria.length > 0) {
      textParts.push(`Acceptance Criteria: ${ticketData.acceptance_criteria.join('; ')}`);
    }

    const text = textParts.join('\n');
    return await this.generateEmbedding(text);
  }

  async generateDocEmbedding(docData) {
    // Create a comprehensive text representation of the document
    const textParts = [
      `Document ID: ${docData.doc_id}`,
      `Title: ${docData.title}`,
      `Category: ${docData.category}`,
      `Version: ${docData.version || 1}`
    ];

    if (docData.system) {
      textParts.push(`System: ${docData.system}`);
    }

    if (docData.content) {
      // Limit content to first 2000 characters to avoid token limits
      const truncatedContent = docData.content.substring(0, 2000);
      textParts.push(`Content: ${truncatedContent}`);
    }

    const text = textParts.join('\n');
    return await this.generateEmbedding(text);
  }

  async generateQueryEmbedding(query) {
    // For search queries, we can enhance them slightly
    const enhancedQuery = `Search query: ${query}`;
    return await this.generateEmbedding(enhancedQuery);
  }

  // Utility method to calculate cosine similarity (for local filtering if needed)
  cosineSimilarity(vecA, vecB) {
    if (vecA.length !== vecB.length) {
      throw new Error('Vectors must have the same length');
    }

    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < vecA.length; i++) {
      dotProduct += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }

    normA = Math.sqrt(normA);
    normB = Math.sqrt(normB);

    if (normA === 0 || normB === 0) {
      return 0;
    }

    return dotProduct / (normA * normB);
  }
}