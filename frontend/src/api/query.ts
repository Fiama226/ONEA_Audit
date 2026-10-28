export type QueryParams = Record<string, string | number | null | undefined>;

/** Construit une chaîne de requête (`?a=1&q=%C3%A9`) en omettant les valeurs vides. */
export function toQuery(params: QueryParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.append(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
