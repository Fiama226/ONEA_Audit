export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly errors: Record<string, string[]>;

  constructor(status: number, detail: string, errors: Record<string, string[]> = {}) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.errors = errors;
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}
