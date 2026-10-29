import { useState } from "react";
import { useParams } from "react-router-dom";
import { useRole } from "@/auth/useRole";
import { ALERT_CLASS } from "@/components/form/FormField";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useAuditFramework, useFrameworkSnapshot } from "../api";
import { FrameworkStatusPanel } from "../components/FrameworkStatusPanel";
import { MarcTable } from "../components/MarcTable";
import { OpinionDialog } from "../components/OpinionDialog";
import { StrengthsWeaknessesTable } from "../components/StrengthsWeaknessesTable";
import { FrameworkSnapshot } from "../components/FrameworkSnapshot";

const t = fr.analyseVVI;

/** Référentiel d'audit de la mission (onglet) : synthèse, MARC, forces et faiblesses, avis des audités. */
export function AuditFrameworkPage() {
  const { id } = useParams();
  const framework = useAuditFramework(id);
  const validated = framework.data?.statut === "VALIDE";
  const snapshot = useFrameworkSnapshot(id, validated);
  const { is } = useRole();
  const [opinionOpen, setOpinionOpen] = useState(false);

  if (framework.isError) {
    return (
      <div role="alert" className={ALERT_CLASS}>
        <p>{t.loadError}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-2"
          onClick={() => void framework.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  }
  if (framework.isPending || id === undefined) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const data = framework.data;
  if (!data.mes_droits.voir_referentiel && !is("AUDITE")) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {t.noAccess}
      </p>
    );
  }
  if (!data.mes_droits.voir_referentiel) {
    return (
      <EmptyState title={t.notBroadcast} description={t.notBroadcastText} illustration={false} />
    );
  }

  return (
    <section aria-labelledby="framework-title" className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="framework-title" className="text-lg font-semibold">
          {t.printTitle}
        </h2>
        <div className="flex flex-wrap gap-2 print:hidden">
          {data.mes_droits.donner_avis && (
            <Button type="button" onClick={() => setOpinionOpen(true)}>
              {t.giveOpinion}
            </Button>
          )}
          <Button type="button" variant="outline" onClick={() => window.print()}>
            {t.printFramework}
          </Button>
        </div>
      </div>
      <FrameworkStatusPanel framework={data} />
      {validated ? (
        <section aria-labelledby="snapshot-title" className="grid gap-3">
          <h3 id="snapshot-title" className="text-base font-semibold">
            {t.snapshotTitle}
          </h3>
          {snapshot.isError && (
            <p role="alert" className={ALERT_CLASS}>
              {t.snapshotError}
            </p>
          )}
          {snapshot.isPending && (
            <p role="status" className="text-sm text-text-muted">
              {t.snapshotLoading}
            </p>
          )}
          {snapshot.data && <FrameworkSnapshot snapshot={snapshot.data} />}
        </section>
      ) : (
        <>
          <MarcTable missionId={id} editable={false} />
          <StrengthsWeaknessesTable missionId={id} editable={false} />
        </>
      )}
      {data.mes_droits.donner_avis && opinionOpen && (
        <OpinionDialog open onOpenChange={setOpinionOpen} missionId={id} />
      )}
    </section>
  );
}
