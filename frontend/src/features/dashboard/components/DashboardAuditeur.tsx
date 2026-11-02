import { Link } from "react-router-dom";
import { StatusPill } from "@/components/StatusPill";
import { fr } from "@/i18n/fr";
import { STATUT_MISSION_LABELS } from "@/features/missions/labels";
import type { StatutMission } from "@/features/missions/types";
import { DueDateCell } from "@/features/suivi/components/DueDateCell";
import { useDashboardAuditor } from "../api";
import { PageHeader } from "./preview";
import { formatDate, PersonalList, QueryState, Tiles } from "./PersonalList";

const d = fr.dashboard;
const t = fr.tableauxEquipe;
const LINK = "font-medium text-primary underline-offset-2 hover:underline";
/** Numéro de l'étape XII (tests d'audit) : la fiche d'un test se documente à cette étape. */
const TESTS_STEP = 12;

export function DashboardAuditeur() {
  const query = useDashboardAuditor();
  const data = query.data;

  return (
    <>
      <PageHeader title={d.auditeurTitle} userRole="AUDITEUR" />
      <QueryState
        isPending={query.isPending}
        isError={query.isError}
        onRetry={() => void query.refetch()}
      />
      {data && (
        <div className="flex flex-col gap-6">
          <Tiles
            items={[
              { label: t.tileMissions, value: data.mes_missions.length },
              { label: t.tileSteps, value: data.mes_etapes_en_cours.length },
              { label: t.tileTests, value: data.mes_tests_a_documenter.length },
              { label: t.tileToVerify, value: data.actions_a_verifier.length },
            ]}
          />
          <PersonalList
            title={t.missionsTitle}
            empty={t.missionsEmpty}
            columns={[
              { label: t.colReference },
              { label: t.colMission },
              { label: t.colStatus },
              { label: t.colEndDate },
            ]}
            rows={data.mes_missions.map((m) => ({
              key: m.mission_id,
              cells: [
                <Link key="r" className={LINK} to={`/missions/${m.mission_id}`}>
                  {m.reference || m.titre}
                </Link>,
                m.titre,
                STATUT_MISSION_LABELS[m.statut as StatutMission] ?? m.statut,
                <DueDateCell key="d" echeance={m.date_fin_prevue} />,
              ],
            }))}
          />
          <PersonalList
            title={t.stepsTitle}
            empty={t.stepsEmpty}
            columns={[{ label: t.colMission }, { label: t.colStep }, { label: t.colEndDate }]}
            rows={data.mes_etapes_en_cours.map((e) => ({
              key: `${e.mission_id}-${e.numero}`,
              cells: [
                e.reference,
                <Link key="s" className={LINK} to={`/missions/${e.mission_id}/etapes/${e.numero}`}>
                  {t.stepLabel.replace("{romain}", e.romain).replace("{libelle}", e.libelle)}
                </Link>,
                <span key="d" className="inline-flex flex-wrap items-center gap-2">
                  <DueDateCell echeance={e.date_fin_prevue} />
                  {e.en_retard && <StatusPill label={t.stepLate} tone="danger" />}
                </span>,
              ],
            }))}
          />
          <PersonalList
            title={t.testsTitle}
            empty={t.testsEmpty}
            columns={[{ label: t.colMission }, { label: t.colTest }, { label: t.colSheet }]}
            rows={data.mes_tests_a_documenter.map((x) => ({
              key: x.test_id,
              cells: [
                x.reference,
                <Link
                  key="t"
                  className={LINK}
                  to={`/missions/${x.mission_id}/etapes/${TESTS_STEP}`}
                >
                  {`${x.code} — ${x.libelle}`}
                </Link>,
                x.sans_fiche ? t.noSheet : t.sheetStarted,
              ],
            }))}
          />
          <PersonalList
            title={t.toVerifyTitle}
            empty={t.toVerifyEmpty}
            columns={[{ label: t.colMission }, { label: t.colAction }, { label: t.colDeclaredOn }]}
            rows={data.actions_a_verifier.map((a) => ({
              key: a.suivi_id,
              cells: [
                a.reference,
                <Link key="a" className={LINK} to={`/recommandations/actions/${a.suivi_id}`}>
                  {a.libelle}
                </Link>,
                formatDate(a.declaree_le),
              ],
            }))}
          />
        </div>
      )}
    </>
  );
}
