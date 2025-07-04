
export class FederationError extends Error {
  public readonly code: string;
  public readonly status: number;

  constructor(message: string, code: string, status: number = 500) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.status = status;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class ToolNotFoundError extends FederationError {
  constructor(toolName: string) {
    super(`Tool "${toolName}" not found.`, 'TOOL_NOT_FOUND', 404);
  }
}

export class InvalidToolInputError extends FederationError {
  constructor(message: string, details?: any) {
    super(`Invalid tool input: ${message}`, 'INVALID_INPUT', 400);
  }
}

export class UpstreamServiceError extends FederationError {
  constructor(serviceName: string, originalError: Error) {
    super(`Error from upstream service "${serviceName}": ${originalError.message}`, 'UPSTREAM_SERVICE_ERROR', 502);
  }
}

export class CacheError extends FederationError {
  constructor(message: string) {
    super(message, 'CACHE_ERROR', 500);
  }
}
