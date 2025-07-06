/**
 * Response Handler Utility
 * Standardizes response formatting for MCP tools
 */

class ResponseHandler {
  /**
   * Format a success response
   * @param {string} message - Success message
   * @param {Object} data - Response data
   * @param {Object} metadata - Additional metadata
   * @returns {Object} Formatted success response
   */
  static success(message, data = null, metadata = {}) {
    const response = {
      success: true,
      message,
      timestamp: new Date().toISOString()
    };

    if (data !== null) {
      response.data = data;
    }

    if (Object.keys(metadata).length > 0) {
      response.metadata = metadata;
    }

    console.log('[ResponseHandler] Success:', JSON.stringify(response, null, 2));
    return response;
  }

  /**
   * Format an error response
   * @param {string} message - Error message
   * @param {Error|string} error - Error object or string
   * @param {string} code - Error code
   * @returns {Object} Formatted error response
   */
  static error(message, error = null, code = 'UNKNOWN_ERROR') {
    const response = {
      success: false,
      error: {
        message,
        code,
        timestamp: new Date().toISOString()
      }
    };

    if (error) {
      if (error instanceof Error) {
        response.error.details = {
          name: error.name,
          message: error.message,
          stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
        };
      } else {
        response.error.details = error;
      }
    }

    console.error('[ResponseHandler] Error:', JSON.stringify(response, null, 2));
    return response;
  }

  /**
   * Format a validation error response
   * @param {string} message - Validation error message
   * @param {Array} errors - Array of validation errors
   * @returns {Object} Formatted validation error response
   */
  static validationError(message, errors = []) {
    return this.error(message, { validationErrors: errors }, 'VALIDATION_ERROR');
  }

  /**
   * Format a not found error response
   * @param {string} resource - Resource type
   * @param {string} identifier - Resource identifier
   * @returns {Object} Formatted not found error response
   */
  static notFound(resource, identifier) {
    return this.error(
      `${resource} not found`,
      { resource, identifier },
      'NOT_FOUND'
    );
  }

  /**
   * Format a conflict error response
   * @param {string} message - Conflict message
   * @param {Object} conflictData - Data about the conflict
   * @returns {Object} Formatted conflict error response
   */
  static conflict(message, conflictData = {}) {
    return this.error(message, conflictData, 'CONFLICT');
  }

  /**
   * Format a partial success response
   * @param {string} message - Success message
   * @param {Object} results - Results with successes and failures
   * @returns {Object} Formatted partial success response
   */
  static partialSuccess(message, results) {
    const response = {
      success: true,
      partial: true,
      message,
      results,
      timestamp: new Date().toISOString()
    };

    console.log('[ResponseHandler] Partial Success:', JSON.stringify(response, null, 2));
    return response;
  }

  /**
   * Check if a response is successful
   * @param {Object} response - Response object
   * @returns {boolean} True if successful
   */
  static isSuccess(response) {
    return response && response.success === true;
  }

  /**
   * Check if a response is an error
   * @param {Object} response - Response object
   * @returns {boolean} True if error
   */
  static isError(response) {
    return response && response.success === false;
  }

  /**
   * Extract data from a response
   * @param {Object} response - Response object
   * @returns {*} Data from response or null
   */
  static getData(response) {
    return this.isSuccess(response) ? response.data : null;
  }

  /**
   * Extract error message from a response
   * @param {Object} response - Response object
   * @returns {string} Error message or empty string
   */
  static getErrorMessage(response) {
    if (this.isError(response) && response.error) {
      return response.error.message || '';
    }
    return '';
  }
}

export default ResponseHandler;