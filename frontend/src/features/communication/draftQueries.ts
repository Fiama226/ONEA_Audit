import { useQuery } from "@tanstack/react-query";
import { fetchAllPages } from "@/api/allPages";
import { communicationKeys } from "./keys";
import type { RapportProvisoire } from "./types";

/** Rapports provisoires d'une mission (l'audité ne connaît pas l'identifiant du rapport). */
export function useMissionDrafts(missionId: string | undefined) {
  return useQuery({
    queryKey: [...communicationKeys.mission(missionId), "drafts"],
    queryFn: () => fetchAllPages<RapportProvisoire>("draft-reports", { mission: missionId }),
    enabled: missionId !== undefined,
  });
}

/** Dernier rapport provisoire transmis (numéro le plus élevé), sinon `undefined`. */
export function latestDraft(drafts: readonly RapportProvisoire[]): RapportProvisoire | undefined {
  return drafts.reduce<RapportProvisoire | undefined>(
    (best, d) => (best === undefined || d.numero > best.numero ? d : best),
    undefined,
  );
}

/** Date AAAA-MM-JJ de la date limite à partir d'un délai en jours (fuseau de l'application). */
export function deadlineIso(days: number, now: Date = new Date()): string {
  return new Date(now.getTime() + days * 86_400_000).toISOString();
}
