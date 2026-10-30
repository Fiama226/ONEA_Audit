import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["constats"] as const;

/** Clés TanStack Query des constats ; `mission(id)` préfixe toutes les clés d'une mission. */
export const constatKeys = {
  all: ROOT as QueryKey,
  mission: (missionId: string | undefined) => [...ROOT, missionId] as QueryKey,
  list: (missionId: string | undefined, params?: object) =>
    [...ROOT, missionId, "list", params ?? null] as QueryKey,
  detail: (id: string | undefined) => [...ROOT, "detail", id] as QueryKey,
  responses: (constatId: string | undefined) => [...ROOT, "responses", constatId] as QueryKey,
  recommendations: (missionId: string | undefined) =>
    [...ROOT, missionId, "recommendations"] as QueryKey,
};
