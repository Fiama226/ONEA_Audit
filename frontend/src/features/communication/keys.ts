import type { QueryKey } from "@tanstack/react-query";

const ROOT = ["communication"] as const;

/** Clés TanStack Query de la communication ; `mission(id)` préfixe les clés d'une mission. */
export const communicationKeys = {
  all: ROOT as QueryKey,
  mission: (missionId: string | undefined) => [...ROOT, "mission", missionId] as QueryKey,
  report: (id: string | undefined) => [...ROOT, "report", id] as QueryKey,
  missionReport: (missionId: string | undefined) =>
    [...ROOT, "mission", missionId, "report"] as QueryKey,
  preview: (id: string | undefined) => [...ROOT, "report", id, "preview"] as QueryKey,
  validationText: (id: string | undefined) =>
    [...ROOT, "report", id, "validation-text"] as QueryKey,
  drafts: (rapportId: string | undefined) => [...ROOT, "drafts", rapportId] as QueryKey,
  draftResponses: (params?: object) => [...ROOT, "draft-responses", params ?? null] as QueryKey,
  draftResponseText: (provisoireId: string | undefined, constatId: string | undefined) =>
    [...ROOT, "draft-response-text", provisoireId, constatId] as QueryKey,
  recipients: (rapportId: string | undefined) => [...ROOT, "recipients", rapportId] as QueryKey,
  distributed: (params?: object) => [...ROOT, "distributed", params ?? null] as QueryKey,
};
