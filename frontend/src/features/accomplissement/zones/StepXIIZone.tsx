import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { useRole } from "@/auth/useRole";
import { useAuth } from "@/auth/useAuth";
import { MotifDialog } from "@/features/missions/components/MotifDialog";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { useAbandonTest, usePlannedTests, useSaveTestSheet, useWorkPrograms } from "../api";
import { ComplementaryTestDialog } from "../components/ComplementaryTestDialog";
import { ConclusionBadge } from "../components/ConclusionBadge";
import { FicheStatusBadge } from "../components/FicheStatusBadge";
import type { TestPrevu } from "../types";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.fiches;

/** Étape XII : documentation des tests, tests complémentaires et abandons (D5, D6). */
export function StepXIIZone({ mission, step }: ZoneProps) {
  const id = `zone-XII-${step.id}`;
  const navigate = useNavigate();
  const { me } = useAuth();
  const { is } = useRole();
  const tests = usePlannedTests({ mission: mission.id });
  const programs = useWorkPrograms(mission.id);
  const create = useSaveTestSheet();
  const abandon = useAbandonTest();
  const [mine, setMine] = useState<boolean | null>(null);
  const [adding, setAdding] = useState(false);
  const [abandoning, setAbandoning] = useState<TestPrevu | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Un auditeur ne voit par défaut que ses tests ; le choix explicite prévaut ensuite.
  const onlyMine = mine ?? is("AUDITEUR");
  const complementPrograms = (programs.data?.results ?? []).filter((program) =>
    program.actions_possibles.includes("AJOUTER_COMPLEMENTAIRE"),
  );

  async function document(test: TestPrevu) {
    setError(null);
    try {
      const fiche = await create.mutateAsync({ missionId: mission.id, data: { test: test.id } });
      void navigate(`/missions/${mission.id}/fiches/${fiche.id}`);
    } catch (e) {
      setError(isApiError(e) ? e.detail : t.createError);
    }
  }

  let body;
  if (tests.isPending) {
    body = <p role="status">{t.loading}</p>;
  } else if (tests.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else {
    const rows = tests.data.results.filter((test) => !onlyMine || test.auditeur === me?.id);
    body = (
      <>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t.filterLabel}>
          <Button
            type="button"
            size="sm"
            variant={onlyMine ? "default" : "outline"}
            aria-pressed={onlyMine}
            onClick={() => setMine(true)}
          >
            {t.myTests}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={onlyMine ? "outline" : "default"}
            aria-pressed={!onlyMine}
            onClick={() => setMine(false)}
          >
            {t.allTests}
          </Button>
          {complementPrograms.length > 0 && (
            <Button type="button" size="sm" className="ml-auto" onClick={() => setAdding(true)}>
              {t.addComplementary}
            </Button>
          )}
        </div>
        {error && (
          <p role="alert" className={ALERT_CLASS}>
            {error}
          </p>
        )}
        {rows.length === 0 ? (
          <p className="text-sm text-text-muted">{onlyMine ? t.noMyTests : t.noTests}</p>
        ) : (
          <ScrollRegion label={t.testsTable}>
            <table className="w-full text-left text-sm" aria-label={t.testsTable}>
              <thead>
                <tr className="border-b border-border text-xs text-text-muted">
                  <th scope="col" className="py-2 pr-3">
                    {t.code}
                  </th>
                  <th scope="col" className="py-2 pr-3">
                    {t.label}
                  </th>
                  <th scope="col" className="py-2 pr-3">
                    {t.auditor}
                  </th>
                  <th scope="col" className="py-2 pr-3">
                    {t.sheet}
                  </th>
                  <th scope="col" className="py-2 pr-3">
                    {t.conclusion}
                  </th>
                  <th scope="col" className="py-2">
                    {t.actions}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((test) => {
                  const abandoned = test.statut === "ABANDONNE";
                  return (
                    <tr key={test.id} className="border-b border-border align-top">
                      <td className="py-2 pr-3">{test.code}</td>
                      <td className="py-2 pr-3">
                        {test.libelle}
                        {test.complementaire && (
                          <span className="ml-2 text-xs text-text-muted">({t.complementary})</span>
                        )}
                        {abandoned && test.motif_abandon && (
                          <p className="text-xs text-text-muted">
                            {t.abandonedReason} : {test.motif_abandon}
                          </p>
                        )}
                      </td>
                      <td className="py-2 pr-3">{test.auditeur_detail?.nom_complet ?? "—"}</td>
                      <td className="py-2 pr-3">
                        {abandoned ? (
                          t.abandoned
                        ) : test.fiche ? (
                          <FicheStatusBadge statut={test.fiche.statut} />
                        ) : (
                          t.toDocument
                        )}
                      </td>
                      <td className="py-2 pr-3">
                        <ConclusionBadge conclusion={test.fiche?.conclusion} />
                      </td>
                      <td className="py-2">
                        <div className="flex flex-wrap gap-1">
                          {!abandoned && test.fiche && (
                            <Link
                              className="text-primary underline"
                              to={`/missions/${mission.id}/fiches/${test.fiche.id}`}
                              aria-label={`${t.openSheet} ${test.code}`}
                            >
                              {t.openSheet}
                            </Link>
                          )}
                          {!abandoned && !test.fiche && mission.mes_droits.contribuer && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={create.isPending}
                              aria-label={`${t.document} ${test.code}`}
                              onClick={() => void document(test)}
                            >
                              {t.document}
                            </Button>
                          )}
                          {test.actions_possibles.includes("ABANDONNER") && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              aria-label={`${t.abandon} ${test.code}`}
                              onClick={() => setAbandoning(test)}
                            >
                              {t.abandon}
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </>
    );
  }

  return (
    <section aria-labelledby={id} className="grid gap-4">
      <h3 id={id} className="text-base font-semibold">
        {t.xiiTitle}
      </h3>
      <p className="text-sm text-text-muted">{t.xiiHelp}</p>
      {body}
      {adding && (
        <ComplementaryTestDialog
          open
          onOpenChange={setAdding}
          missionId={mission.id}
          programs={complementPrograms}
        />
      )}
      {abandoning && (
        <MotifDialog
          open
          onOpenChange={(open) => !open && setAbandoning(null)}
          title={`${t.abandonTitle} ${abandoning.code}`}
          description={t.abandonDescription}
          confirmLabel={t.abandonConfirm}
          onSubmit={(motif) =>
            abandon.mutateAsync({ id: abandoning.id, missionId: mission.id, motif })
          }
        />
      )}
    </section>
  );
}
