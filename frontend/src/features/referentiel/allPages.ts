import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { toQuery } from "@/api/query";
import { referentielKeys, type DirectionParams, type ProcessParams } from "./api";
import type { Direction, Page, Processus } from "./types";

const PAGE_SIZE = 200;
/** Garde-fou contre une boucle infinie si le serveur renvoie toujours un `next`. */
const MAX_PAGES = 50;

export type AllPages<T> = { results: T[]; count: number };

/** Charge toutes les pages d'une liste paginée (taille de page maximale, suit `next`). */
export async function fetchAllPages<T>(
  resource: string,
  params: Record<string, string | number | undefined> = {},
): Promise<AllPages<T>> {
  const results: T[] = [];
  let count = 0;
  for (let page = 1; page <= MAX_PAGES; page++) {
    const data = await apiFetch<Page<T>>(
      `/api/v1/${resource}/${toQuery({ ...params, page, page_size: PAGE_SIZE })}`,
    );
    count = data.count;
    results.push(...data.results);
    if (!data.next || data.results.length === 0) break;
  }
  return { results, count };
}

type Unpaged<P> = Omit<P, "page" | "page_size">;

/** Toutes les directions et départements (sans pagination visible). */
export function useAllDirections(params: Unpaged<DirectionParams> = {}) {
  return useQuery({
    queryKey: [...referentielKeys.directions(), "all", params],
    queryFn: () => fetchAllPages<Direction>("directions", params),
  });
}

/** Tous les processus (sans pagination visible). */
export function useAllProcesses(params: Unpaged<ProcessParams> = {}) {
  return useQuery({
    queryKey: [...referentielKeys.processes(), "all", params],
    queryFn: () => fetchAllPages<Processus>("processes", params),
  });
}
