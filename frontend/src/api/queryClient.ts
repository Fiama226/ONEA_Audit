import { QueryClient } from "@tanstack/react-query";
import { isApiError } from "./errors";

/** Les erreurs 4xx sont définitives (introuvable, refusé) : inutile de les rejouer ; une panne, une seule fois. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isApiError(error) && error.status >= 400 && error.status < 500) return false;
  return failureCount < 1;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: shouldRetry } } });
}
