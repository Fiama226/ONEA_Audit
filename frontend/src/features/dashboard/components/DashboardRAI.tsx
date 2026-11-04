import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { BarList, StackedBar, StatTile } from "@/components/charts";
import { PrintLayout } from "@/components/print/PrintLayout";
import { RiskMatrix, type RiskMatrixCell } from "@/components/RiskMatrix";
import { fr } from "@/i18n/fr";
import { useDashboardRai, type TableauRai } from "../api";
import { useYearParam } from "../year";
import { CELL, DashError, DashLoading, DashSection, DashTable, ROW } from "./DashParts";
import { DecisionQueue } from "./DecisionQueue";
import { LateMissionsTable } from "./LateMissionsTable";
import { PageHeader, PreviewCard, SkeletonTable } from "./preview";
import { YearFilter } from "./YearFilter";

const d = fr.dashboard;
const t = fr.tableauxDirection;

/** Missions « en cours » : même définition que le serveur (hors brouillon, planifiée, diffusée, figée). */
const IN_PROGRESS = ["EN_PLANIFICATION", "EN_ACCOMPLISSEMENT", "EN_COMMUNICATION"];

function LoadingRAI() {
  return (
    <DashLoading>
      <div aria-hidden="true" className="grid grid-cols-12 items-start gap-6">
        <PreviewCard title={d.missionsByPhase} span={8}>
          <SkeletonTable
            columns={[
              { label: t.colReference, width: 80 },
              { label: t.colTitle, width: 150 },
              { label: t.colStatus, width: 100 },
            ]}
          />
        </PreviewCard>
        <PreviewCard title={t.decisionQueue} span={4}>
          <SkeletonTable columns={[{ label: t.decisionQueue, width: 120 }]} />
        </PreviewCard>
      </div>
    </DashLoading>
  );
}

function asCells(data: TableauRai): RiskMatrixCell[] {
  const ok = (n: number): n is 1 | 2 | 3 | 4 | 5 => Number.isInteger(n) && n >= 1 && n <= 5;
  return data.cartographie.cellules.flatMap((c) =>
    ok(c.probabilite) && ok(c.impact)
      ? [{ probability: c.probabilite, impact: c.impact, count: c.nombre }]
      : [],
  );
}

function Content({ data }: { data: TableauRai }) {
  const inProgress = data.missions_par_statut
    .filter((m) => IN_PROGRESS.includes(m.statut))
    .reduce((sum, m) => sum + m.nombre, 0);
  const actionsLate = data.actions_par_direction.reduce((sum, r) => sum + r.en_retard, 0);
  const directions = data.actions_par_direction;
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label={t.tileMissionsInProgress} value={inProgress} />
        <StatTile
          label={t.tileMissionsLate}
          value={data.missions_en_retard.length}
          icon={AlertTriangle}
          tone="danger"
          hint={t.lateStepsNote.replace("{n}", String(data.etapes_en_retard))}
        />
        <StatTile label={t.tileMilestones} value={data.jalons_a_valider.length} />
        <StatTile
          label={t.tileActionsLate}
          value={actionsLate}
          icon={AlertTriangle}
          tone="danger"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        <DashSection title={t.missionsByStatus} className="lg:col-span-6">
          {data.missions_par_statut.length === 0 ? (
            <p className="text-sm text-text-muted">{t.missionsByStatusEmpty}</p>
          ) : (
            <BarList
              ariaLabel={t.missionsByStatus}
              data={data.missions_par_statut.map((m) => ({
                key: m.statut,
                label: m.libelle,
                value: m.nombre,
                href: `/missions?statut=${m.statut}`,
              }))}
            />
          )}
        </DashSection>
        <div className="lg:col-span-6">
          <DecisionQueue queue={data.file_decisions} />
        </div>
      </div>

      <DashSection title={t.actionsByDirection}>
        {directions.length === 0 ? (
          <p className="text-sm text-text-muted">{t.actionsByDirectionEmpty}</p>
        ) : (
          <>
            <StackedBar
              ariaLabel={t.actionsByDirection}
              rows={directions.map((r) => ({
                key: r.direction_id,
                label: `${r.code} — ${r.libelle}`,
                segments: {
                  done: r.cloturees,
                  open: r.ouvertes_dans_les_delais,
                  late: r.en_retard,
                },
              }))}
            />
            <div className="mt-4">
              <DashTable
                caption={t.abandonedDetail}
                isEmpty={false}
                empty=""
                columns={[
                  { label: t.colDirection },
                  { label: t.colClosed, numeric: true },
                  { label: t.colOpen, numeric: true },
                  { label: t.colLate, numeric: true },
                  { label: t.colAbandoned, numeric: true },
                ]}
              >
                {directions.map((r) => (
                  <tr key={r.direction_id} className={ROW}>
                    <td className={CELL}>{r.code}</td>
                    <td className={`${CELL} text-right tabular-nums`}>{r.cloturees}</td>
                    <td className={`${CELL} text-right tabular-nums`}>
                      {r.ouvertes_dans_les_delais}
                    </td>
                    <td className={`${CELL} text-right tabular-nums`}>{r.en_retard}</td>
                    <td className={`${CELL} text-right tabular-nums`}>{r.abandonnees}</td>
                  </tr>
                ))}
              </DashTable>
            </div>
          </>
        )}
      </DashSection>

      <LateMissionsTable missions={data.missions_en_retard} />

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        <DashSection title={t.milestonesList} className="lg:col-span-7">
          {data.jalons_a_valider.length === 0 ? (
            <p className="text-sm text-text-muted">{t.milestonesEmpty}</p>
          ) : (
            <ul className="m-0 list-none p-0">
              {data.jalons_a_valider.map((j) => (
                <li
                  key={`${j.mission_id}-${j.numero}`}
                  className="flex flex-wrap items-center gap-x-3 border-b border-border py-2 text-sm last:border-b-0"
                >
                  <Link
                    to={`/missions/${j.mission_id}/etapes/${j.numero}`}
                    className="font-medium underline"
                  >
                    {j.reference} · {j.romain}
                  </Link>
                  <span>{j.libelle}</span>
                  {j.terminee_le && (
                    <span className="text-xs text-text-muted">
                      {t.milestoneDoneOn.replace(
                        "{date}",
                        new Date(j.terminee_le).toLocaleDateString("fr-FR", {
                          timeZone: "Africa/Ouagadougou",
                        }),
                      )}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </DashSection>
        <DashSection title={t.criticality} className="lg:col-span-5">
          <RiskMatrix cells={asCells(data)} />
        </DashSection>
      </div>
    </div>
  );
}

export function DashboardRAI() {
  const [annee, setAnnee] = useYearParam();
  const query = useDashboardRai(annee);
  return (
    <PrintLayout title={t.printTitleRai} orientation="paysage">
      <PageHeader title={d.raiTitle} userRole="RAI" annee={annee} />
      <YearFilter value={annee} onChange={setAnnee} />
      {query.isPending ? (
        <LoadingRAI />
      ) : query.isError ? (
        <DashError onRetry={() => void query.refetch()} />
      ) : (
        <Content data={query.data} />
      )}
    </PrintLayout>
  );
}
