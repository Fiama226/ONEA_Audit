import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["dashboard"] as const;

/** Clés TanStack Query des tableaux de bord ; `all` sert à l'invalidation après une mutation du suivi. */
export const dashboardKeys = {
  all: ROOT as QueryKey,
  rai: (annee?: number) => [...ROOT, "rai", annee ?? null] as QueryKey,
  dg: (annee?: number) => [...ROOT, "dg", annee ?? null] as QueryKey,
  auditor: () => [...ROOT, "auditor"] as QueryKey,
  auditee: () => [...ROOT, "auditee"] as QueryKey,
};
