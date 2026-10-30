import { Link } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { DueDateCell } from "@/features/suivi/components/DueDateCell";
import { SuiviStatusBadge } from "@/features/suivi/components/SuiviStatusBadge";
import { STATUT_REPORT_LABELS } from "@/features/suivi/labels";
import type { StatutDemandeReport, StatutSuivi } from "@/features/suivi/types";
import { useDashboardAuditee } from "../api";
import { PageHeader } from "./preview";
import { formatDate, PersonalList, QueryState, Tiles } from "./PersonalList";

const d = fr.dashboard;
const t = fr.tableauxEquipe;
const LINK = "font-medium text-primary underline-offset-2 hover:underline";
const OPEN = new Set(["A_LANCER", "EN_COURS", "REALISEE", "VERIFIEE", "ABANDON_PROPOSE"]);

export function DashboardAudite() {
  const query = useDashboardAuditee();
  const data = query.data;
  const actions = data
    ? [...data.mes_actions].sort((a, b) => a.echeance.localeCompare(b.echeance))
    : [];

  return (
    <>
      <PageHeader title={d.auditeTitle} userRole="AUDITE" />
      <QueryState
        isPending={query.isPending}
        isError={query.isError}
        onRetry={() => void query.refetch()}
      />
      {data && (
        <div className="flex flex-col gap-6">
          <Tiles
            items={[
              { label: t.tileFindings, value: data.constats_a_repondre.length },
              { label: t.tileOpenActions, value: actions.filter((a) => OPEN.has(a.statut)).length },
              { label: t.tileLate, value: actions.filter((a) => a.en_retard).length },
            ]}
          />
          <PersonalList
            title={t.findingsTitle}
            empty={t.findingsEmpty}
            columns={[
              { label: t.colMission },
              { label: t.colFinding },
              { label: t.colCycle },
              { label: t.colSubmittedOn },
            ]}
            rows={data.constats_a_repondre.map((c) => ({
              key: c.constat_id,
              cells: [
                c.mission_reference,
                <Link
                  key="c"
                  className={LINK}
                  to={`/missions/${c.mission_id}/constats/${c.constat_id}`}
                >
                  {`${c.reference} — ${c.titre}`}
                </Link>,
                c.cycle,
                formatDate(c.soumis_le),
              ],
            }))}
          />
          <PersonalList
            title={t.actionsTitle}
            empty={t.actionsEmpty}
            columns={[
              { label: t.colMission },
              { label: t.colAction },
              { label: t.colDueDate },
              { label: t.colStatus },
            ]}
            rows={actions.map((a) => ({
              key: a.suivi_id,
              cells: [
                a.reference,
                <Link key="a" className={LINK} to={`/recommandations/actions/${a.suivi_id}`}>
                  {a.libelle}
                </Link>,
                <DueDateCell
                  key="d"
                  echeance={a.echeance}
                  enRetard={a.en_retard}
                  joursRetard={a.jours_retard}
                />,
                <SuiviStatusBadge key="s" statut={a.statut as StatutSuivi} />,
              ],
            }))}
          />
          <PersonalList
            title={t.extensionsTitle}
            empty={t.extensionsEmpty}
            columns={[
              { label: t.colAction },
              { label: t.colCurrentDue },
              { label: t.colNewDue },
              { label: t.colRequestStatus },
            ]}
            rows={data.mes_demandes_report.map((r) => ({
              key: r.demande_id,
              cells: [
                <Link key="a" className={LINK} to={`/recommandations/actions/${r.suivi_id}`}>
                  {r.reference}
                </Link>,
                <DueDateCell key="c" echeance={r.echeance_actuelle} />,
                <DueDateCell key="n" echeance={r.nouvelle_echeance} />,
                STATUT_REPORT_LABELS[r.statut as StatutDemandeReport] ?? r.statut,
              ],
            }))}
          />
        </div>
      )}
    </>
  );
}
