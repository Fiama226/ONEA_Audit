import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["accomplissement"] as const;

/** Clés TanStack Query de l'accomplissement ; `mission(id)` préfixe toutes les clés d'une mission. */
export const accomplissementKeys = {
  all: ROOT as QueryKey,
  mission: (missionId: string | undefined) => [...ROOT, missionId] as QueryKey,
  programs: (missionId: string | undefined) => [...ROOT, missionId, "programs"] as QueryKey,
  summary: (missionId: string | undefined) => [...ROOT, missionId, "summary"] as QueryKey,
  snapshots: (missionId: string | undefined) => [...ROOT, missionId, "snapshots"] as QueryKey,
  tests: (missionId: string | undefined, params?: object) =>
    [...ROOT, missionId, "tests", params ?? null] as QueryKey,
  sheets: (missionId: string | undefined, params?: object) =>
    [...ROOT, missionId, "sheets", params ?? null] as QueryKey,
  sheet: (id: string | undefined) => [...ROOT, "sheet", id] as QueryKey,
  evidence: (ficheId: string | undefined) => [...ROOT, "evidence", ficheId] as QueryKey,
};
