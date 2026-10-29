import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["documents"] as const;

/** Clés TanStack Query des documents ; appelées sans argument, elles servent de préfixe d'invalidation. */
export const documentKeys = {
  all: ROOT as QueryKey,
  types: () => [...ROOT, "types"] as QueryKey,
  templates: () => [...ROOT, "templates"] as QueryKey,
  templateList: (params: object) => [...ROOT, "templates", "list", params] as QueryKey,
  template: (id: string | undefined) => [...ROOT, "templates", "detail", id] as QueryKey,
  numbering: () => [...ROOT, "numbering"] as QueryKey,
  lists: () => [...ROOT, "list"] as QueryKey,
  list: (params: object) => [...ROOT, "list", params] as QueryKey,
  document: (id: string | undefined) => [...ROOT, "detail", id] as QueryKey,
  availables: () => [...ROOT, "available"] as QueryKey,
  available: (missionId: string | undefined) => [...ROOT, "available", missionId] as QueryKey,
  version: (id: string | undefined) => [...ROOT, "version", id] as QueryKey,
  consultations: (versionId: string | undefined) =>
    [...ROOT, "consultations", versionId] as QueryKey,
};
