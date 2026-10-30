import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["suivi"] as const;

/** Clés TanStack Query du suivi ; `all` préfixe toutes les clés (listes, détail, preuves, reports). */
export const suiviKeys = {
  all: ROOT as QueryKey,
  actions: (params?: object) => [...ROOT, "actions", params ?? null] as QueryKey,
  action: (id: string | undefined) => [...ROOT, "action", id] as QueryKey,
  events: (id: string | undefined) => [...ROOT, "action", id, "events"] as QueryKey,
  recommendations: (params?: object) => [...ROOT, "recommendations", params ?? null] as QueryKey,
  evidence: (actionId: string | undefined) => [...ROOT, "action", actionId, "evidence"] as QueryKey,
  extensions: (params?: object) => [...ROOT, "extensions", params ?? null] as QueryKey,
  missionsToClose: () => [...ROOT, "missions-to-close"] as QueryKey,
};
