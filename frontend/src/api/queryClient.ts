import { QueryClient } from "@tanstack/react-query";
import { isApiError } from "./errors";

const MAX_RETRIES = 2;

/**
 * Seules les pannes passagères (réseau, erreur serveur) méritent un nouvel essai. Une erreur
 * client (introuvable, interdit, donnée invalide) ne changera pas : réessayer ne ferait
 * qu'afficher un chargement pendant plusieurs secondes avant le vrai message.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isApiError(error) && error.status >= 400 && error.status < 500) return false;
  return failureCount < MAX_RETRIES;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: shouldRetry } } });
}
