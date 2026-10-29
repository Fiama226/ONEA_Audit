import { Link } from "react-router-dom";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { RiskLevelBadge } from "@/features/referentiel/components/RiskLevelBadge";
import { fr } from "@/i18n/fr";
import { useProposedRisks } from "../api";

const m = fr.missionEtapes;

/** Risques créés par les missions, en lecture seule pour le RAI (aucune insertion automatique). */
export function ProposedRisksPanel() {
  const proposed = useProposedRisks();
  const rows = proposed.data?.results ?? [];
  return (
    <section aria-labelledby="proposed-risks-title" className="grid gap-3 print:hidden">
      <h3 id="proposed-risks-title" className="text-base font-semibold">
        {m.proposedTitle.replace("{n}", String(proposed.data?.count ?? 0))}
      </h3>
      {proposed.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {m.proposedLoadError}
        </p>
      ) : proposed.isLoading ? (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-text-muted">{m.proposedEmpty}</p>
      ) : (
        <>
          <ListIncompleteAlert count={proposed.data?.count ?? 0} loaded={rows.length} />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">{m.proposedCaption}</caption>
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th scope="col" className="py-1 pr-3 font-medium">
                    {m.proposedMission}
                  </th>
                  <th scope="col" className="py-1 pr-3 font-medium">
                    {m.proposedProcess}
                  </th>
                  <th scope="col" className="py-1 pr-3 font-medium">
                    {m.proposedRisk}
                  </th>
                  <th scope="col" className="py-1 pr-3 font-medium">
                    {m.proposedScore}
                  </th>
                  <th scope="col" className="py-1 font-medium">
                    {m.proposedLevel}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-border/60 align-top">
                    <td className="py-1 pr-3">
                      <Link
                        to={`/missions/${r.mission}`}
                        className="font-medium text-primary underline-offset-4 hover:underline"
                      >
                        {r.mission_reference}
                      </Link>
                    </td>
                    <td className="py-1 pr-3">{r.processus_code}</td>
                    <td className="py-1 pr-3">{r.libelle}</td>
                    <td className="py-1 pr-3 tabular-nums">
                      {r.probabilite}×{r.impact}
                    </td>
                    <td className="py-1">
                      <RiskLevelBadge niveau={r.niveau} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
