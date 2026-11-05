import { useQuery } from "@tanstack/react-query";
import { fetchAllPages } from "@/api/allPages";
import { referentielKeys, useRiskMaps } from "@/features/referentiel/api";
import type { Risque } from "@/features/referentiel/types";

export type RiskChoice = { id: string; label: string; processus: string };

/**
 * Risques proposés comme « risques couverts » d'une mission : ceux de sa cartographie de
 * référence (en modification) ou de la dernière cartographie validée (en création, celle que le
 * serveur retiendra).
 */
export function useCoveredRiskChoices(versionId: string | undefined) {
  const maps = useRiskMaps({ statut: "VALIDEE", ordering: "-annee", page_size: 1 });
  const version = versionId ?? maps.data?.results[0]?.id;
  const risks = useQuery({
    queryKey: [...referentielKeys.risks({ version }), "all"],
    queryFn: () => fetchAllPages<Risque>("risks", { version, ordering: "code" }),
    enabled: version !== undefined,
  });
  const items: RiskChoice[] = (risks.data?.results ?? []).map((r) => ({
    id: r.id,
    label: `${r.code} - ${r.libelle}`,
    processus: r.processus,
  }));
  return {
    items,
    isLoading: maps.isLoading || risks.isLoading,
    isError: maps.isError || risks.isError,
  };
}
