import { apiFetch } from "@/api/client";

type Scalar = string | number | boolean | null | undefined;
export type SuiviQuery = Record<string, Scalar | readonly string[]>;

/**
 * Chaîne de requête du suivi : les listes sont répétées (`statut=A&statut=B`, filtre
 * `MultipleChoiceFilter` du serveur), les booléens deviennent `true` / `false`, les vides sont omis.
 */
export function suiviQuery(params: SuiviQuery): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, item);
    } else {
      search.append(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

const PAGE_SIZE = 200;
const MAX_PAGES = 50;

/** Charge toutes les pages d'une liste du suivi (taille maximale, suit `next`). */
export async function fetchAllFollowUp<T>(
  resource: string,
  params: SuiviQuery = {},
): Promise<{ results: T[]; count: number }> {
  const results: T[] = [];
  let count = 0;
  for (let page = 1; page <= MAX_PAGES; page++) {
    const data = await apiFetch<{ count: number; next?: string | null; results: T[] }>(
      `/api/v1/${resource}/${suiviQuery({ ...params, page, page_size: PAGE_SIZE })}`,
    );
    count = data.count;
    results.push(...data.results);
    if (!data.next || data.results.length === 0) break;
  }
  return { results, count };
}
