import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["recommandations"] as const;

/** Clés TanStack Query du plan d'actions ; `mission(id)` préfixe les clés d'une mission. */
export const recommandationKeys = {
  all: ROOT as QueryKey,
  mission: (missionId: string | undefined) => [...ROOT, "mission", missionId] as QueryKey,
  actions: (params?: object) => [...ROOT, "actions", params ?? null] as QueryKey,
  acceptances: (params?: object) => [...ROOT, "acceptances", params ?? null] as QueryKey,
  commitments: (missionId: string | undefined) =>
    [...ROOT, "mission", missionId, "commitments"] as QueryKey,
  commitmentText: (missionId: string | undefined) =>
    [...ROOT, "mission", missionId, "commitment-text"] as QueryKey,
  summary: (missionId: string | undefined) =>
    [...ROOT, "mission", missionId, "summary"] as QueryKey,
};
