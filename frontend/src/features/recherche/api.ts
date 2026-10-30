import { keepPreviousData, useQuery, type QueryKey } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { ApiError, isApiError } from "@/api/errors";
import { toQuery } from "@/api/query";
import type { components } from "@/api/schema";
import { fr } from "@/i18n/fr";

export type ReponseRecherche = components["schemas"]["ReponseRecherche"];
export type TypeResultat = components["schemas"]["TypeResultatRechercheEnum"];

/** Longueur minimale de la requête (identique au serveur). */
export const MIN_QUERY_LENGTH = 2;

export const rechercheKeys = {
  all: ["recherche"] as QueryKey,
  search: (q: string, types: readonly TypeResultat[]) =>
    ["recherche", "search", q, [...types].sort()] as QueryKey,
};

/** Recherche globale : 429 et 503 sont traduits ; aucune requête sous 2 caractères. */
export function useSearch(q: string, types: readonly TypeResultat[] = []) {
  const term = q.trim();
  return useQuery({
    queryKey: rechercheKeys.search(term, types),
    queryFn: async () => {
      try {
        return await apiFetch<ReponseRecherche>(
          `/api/v1/search/${toQuery({ q: term, types: types.length ? [...types].join(",") : undefined })}`,
        );
      } catch (e) {
        if (isApiError(e) && e.status === 429) {
          throw new ApiError(429, fr.suivi.searchRateLimited);
        }
        if (isApiError(e) && e.status === 503) {
          throw new ApiError(503, fr.suivi.searchUnavailable);
        }
        throw e;
      }
    },
    enabled: term.length >= MIN_QUERY_LENGTH,
    placeholderData: keepPreviousData,
    retry: false,
  });
}
