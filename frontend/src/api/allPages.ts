import { apiFetch } from "./client";
import { toQuery, type QueryParams } from "./query";

const PAGE_SIZE = 200;
/** Garde-fou contre une boucle infinie si le serveur renvoie toujours un `next`. */
const MAX_PAGES = 50;

export type AllPages<T> = { results: T[]; count: number };

/** Charge toutes les pages d'une liste paginée (taille de page maximale, suit `next`). */
export async function fetchAllPages<T>(
  resource: string,
  params: QueryParams = {},
): Promise<AllPages<T>> {
  const results: T[] = [];
  let count = 0;
  for (let page = 1; page <= MAX_PAGES; page++) {
    const data = await apiFetch<{ count: number; next?: string | null; results: T[] }>(
      `/api/v1/${resource}/${toQuery({ ...params, page, page_size: PAGE_SIZE })}`,
    );
    count = data.count;
    results.push(...data.results);
    if (!data.next || data.results.length === 0) break;
  }
  return { results, count };
}
