import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { RiskMatrix, type RiskMatrixCell } from "@/components/RiskMatrix";
import { Button } from "@/components/ui/button";
import { RiskLevelBadge } from "@/features/referentiel/components/RiskLevelBadge";
import { fr } from "@/i18n/fr";
import { useDeleteMissionRisk, useMissionMatrix, useMissionRisks } from "../api";
import { ConfirmActionDialog } from "../components/ConfirmActionDialog";
import { MissionRiskDialog } from "../components/MissionRiskDialog";
import { RiskSelectDialog } from "../components/RiskSelectDialog";
import type { Etape, Mission, RisqueMission } from "../types";
import { ScrollRegion } from "@/components/ui/scroll-region";

const m = fr.missionEtapes;

/** Étapes où le serveur accepte d'ajouter ou de modifier les risques (D15). */
const WRITABLE_STATUSES: readonly string[] = ["EN_COURS", "RENVOYEE"];

function scale(value: string | null): 1 | 2 | 3 | 4 | 5 | null {
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 && n <= 5 ? (n as 1 | 2 | 3 | 4 | 5) : null;
}

function reference(r: RisqueMission): string {
  const { probabilite_reference: p, impact_reference: i } = r;
  if (p === null || i === null || (p === r.probabilite && i === r.impact)) return m.noValue;
  return `${p}×${i}`;
}

/** Étape IV : risques retenus pour la mission, matrice et réévaluation. */
export function StepIVZone({ mission, step }: { mission: Mission; step: Etape }) {
  const [params, setParams] = useSearchParams();
  const risks = useMissionRisks(mission.id);
  const matrix = useMissionMatrix(mission.id);
  const remove = useDeleteMissionRisk();
  const [selecting, setSelecting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<RisqueMission | null>(null);
  const [removing, setRemoving] = useState<RisqueMission | null>(null);

  const writable = mission.mes_droits.contribuer && WRITABLE_STATUSES.includes(step.statut);
  const probabilite = scale(params.get("probabilite"));
  const impact = scale(params.get("impact"));
  const cellFilter = probabilite && impact ? { probability: probabilite, impact } : null;

  const all = risks.data?.results ?? [];
  const rows = cellFilter
    ? all.filter((r) => r.probabilite === cellFilter.probability && r.impact === cellFilter.impact)
    : all;
  const selectedSources = new Set(all.flatMap((r) => (r.risque_source ? [r.risque_source] : [])));
  const cells: RiskMatrixCell[] = (matrix.data?.cellules ?? []).map((c) => ({
    probability: c.probabilite as RiskMatrixCell["probability"],
    impact: c.impact as RiskMatrixCell["impact"],
    count: c.nombre,
    codes: c.codes,
  }));

  function setFilter(next: { probability: number; impact: number } | null) {
    setParams(
      (prev) => {
        const q = new URLSearchParams(prev);
        if (next) {
          q.set("probabilite", String(next.probability));
          q.set("impact", String(next.impact));
        } else {
          q.delete("probabilite");
          q.delete("impact");
        }
        return q;
      },
      { replace: true },
    );
  }

  const titleId = `zone-${step.id}`;
  return (
    <section aria-labelledby={titleId} className="grid gap-4 rounded-md border border-border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={titleId} className="text-base font-semibold">
          {m.riskTitle}
        </h3>
        {writable && (
          <div className="flex flex-wrap gap-2 print:hidden">
            <Button type="button" onClick={() => setSelecting(true)}>
              {mission.cartographie
                ? m.selectRisks.replace("{annee}", String(mission.cartographie.annee))
                : m.selectRisksNoMap}
            </Button>
            <Button type="button" variant="outline" onClick={() => setCreating(true)}>
              {m.addNewRisk}
            </Button>
          </div>
        )}
      </div>
      {!writable && <p className="text-sm text-text-muted print:hidden">{m.readOnlyNote}</p>}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)]">
        <div className="grid min-w-0 content-start gap-2">
          {cellFilter && (
            <p role="status" className="flex items-center gap-3 text-sm">
              {m.filterActive
                .replace("{p}", String(cellFilter.probability))
                .replace("{i}", String(cellFilter.impact))}
              <Button
                type="button"
                variant="link"
                className="h-auto p-0"
                onClick={() => setFilter(null)}
              >
                {m.clearFilter}
              </Button>
            </p>
          )}
          {risks.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {m.riskLoadError}
            </p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-text-muted">
              {risks.isLoading ? fr.common.loading : cellFilter ? m.riskEmptyFiltered : m.riskEmpty}
            </p>
          ) : (
            <ScrollRegion label={m.riskCaption}>
              <table className="w-full text-left text-sm">
                <caption className="sr-only">{m.riskCaption}</caption>
                <thead>
                  <tr className="border-b border-border text-text-muted">
                    <th scope="col" className="py-1 pr-3 font-medium">
                      {m.riskCode}
                    </th>
                    <th scope="col" className="py-1 pr-3 font-medium">
                      {m.riskLabel}
                    </th>
                    <th scope="col" className="py-1 pr-3 font-medium">
                      {fr.refCartographie.colProcessus}
                    </th>
                    <th scope="col" className="py-1 pr-3 font-medium">
                      {fr.refCartographie.colP}
                    </th>
                    <th scope="col" className="py-1 pr-3 font-medium">
                      {fr.refCartographie.colI}
                    </th>
                    <th scope="col" className="py-1 pr-3 font-medium">
                      {fr.refCartographie.colScore}
                    </th>
                    <th scope="col" className="py-1 pr-3 font-medium">
                      {fr.refCartographie.colNiveau}
                    </th>
                    <th scope="col" className="py-1 pr-3 font-medium">
                      {m.riskReference}
                    </th>
                    {writable && (
                      <th scope="col" className="py-1 font-medium print:hidden">
                        {m.riskActions}
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} className="border-b border-border/60 align-top">
                      <td className="py-1 pr-3 font-medium">{r.code_source || m.riskNew}</td>
                      <td className="py-1 pr-3">{r.libelle}</td>
                      <td className="py-1 pr-3">{r.processus_code}</td>
                      <td className="py-1 pr-3 tabular-nums">{r.probabilite}</td>
                      <td className="py-1 pr-3 tabular-nums">{r.impact}</td>
                      <td className="py-1 pr-3 tabular-nums">{r.score}</td>
                      <td className="py-1 pr-3">
                        <RiskLevelBadge niveau={r.niveau} />
                      </td>
                      <td className="py-1 pr-3 tabular-nums">{reference(r)}</td>
                      {writable && (
                        <td className="py-1 print:hidden">
                          <div className="flex flex-wrap gap-1">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              aria-label={`${m.reevaluate} ${r.libelle}`}
                              onClick={() => setEditing(r)}
                            >
                              {m.reevaluate}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              aria-label={`${m.remove} ${r.libelle}`}
                              onClick={() => setRemoving(r)}
                            >
                              {m.remove}
                            </Button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          )}
        </div>
        <div className="min-w-0">
          <h4 className="mb-2 text-sm font-semibold">{m.matrixTitle}</h4>
          {matrix.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {fr.refCartographie.matrixLoadError}
            </p>
          ) : (
            <RiskMatrix
              size="large"
              cells={matrix.isLoading ? [] : cells}
              selected={cellFilter}
              onSelect={(cell) =>
                cellFilter?.probability === cell.probability && cellFilter.impact === cell.impact
                  ? setFilter(null)
                  : setFilter(cell)
              }
            />
          )}
        </div>
      </div>

      {writable && (
        <>
          <RiskSelectDialog
            mission={mission}
            selectedSources={selectedSources}
            open={selecting}
            onOpenChange={setSelecting}
          />
          <MissionRiskDialog mission={mission} open={creating} onOpenChange={setCreating} />
          <MissionRiskDialog
            mission={mission}
            risk={editing ?? undefined}
            open={editing !== null}
            onOpenChange={(open) => !open && setEditing(null)}
          />
          <ConfirmActionDialog
            open={removing !== null}
            onOpenChange={(open) => !open && setRemoving(null)}
            title={m.removeTitle}
            text={m.removeText.replace("{libelle}", removing?.libelle ?? "")}
            confirmLabel={m.remove}
            onConfirm={() =>
              removing
                ? remove.mutateAsync({ id: removing.id, missionId: mission.id })
                : Promise.resolve()
            }
          />
        </>
      )}
    </section>
  );
}
