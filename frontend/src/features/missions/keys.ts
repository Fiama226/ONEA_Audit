import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["missions"] as const;

/** Clés TanStack Query des missions ; appelées sans argument, elles servent de préfixe d'invalidation. */
export const missionKeys = {
  all: ROOT as QueryKey,
  lists: () => [...ROOT, "list"] as QueryKey,
  list: (params: object) => [...ROOT, "list", params] as QueryKey,
  detail: (id: string | undefined) => [...ROOT, "detail", id] as QueryKey,
  defaultAuditees: (id: string | undefined) => [...ROOT, "default-auditees", id] as QueryKey,
  users: (params: object) => [...ROOT, "users", params] as QueryKey,
  assignments: (missionId: string | undefined) => [...ROOT, "assignments", missionId] as QueryKey,
  declarations: (params?: object) =>
    (params ? [...ROOT, "declarations", params] : [...ROOT, "declarations"]) as QueryKey,
  steps: (missionId: string | undefined) => [...ROOT, "steps", missionId] as QueryKey,
  step: (id: string | undefined) => [...ROOT, "step", id] as QueryKey,
  tracking: (missionId: string | undefined) => [...ROOT, "tracking", missionId] as QueryKey,
  meetings: (missionId: string | undefined) => [...ROOT, "meetings", missionId] as QueryKey,
  interviews: (params?: object) =>
    (params ? [...ROOT, "interviews", params] : [...ROOT, "interviews"]) as QueryKey,
  risks: (missionId: string | undefined) => [...ROOT, "risks", missionId] as QueryKey,
  matrix: (missionId: string | undefined) => [...ROOT, "matrix", missionId] as QueryKey,
  proposedRisks: () => [...ROOT, "proposed-risks"] as QueryKey,
};
