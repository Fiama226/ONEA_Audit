import { useState } from "react";
import { useParams } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import { ResultsAgreementCard } from "@/features/accomplissement/components/ResultsAgreementCard";
import { fr } from "@/i18n/fr";
import { useFindings } from "../api";
import { ConstatsTable } from "../components/ConstatsTable";

const t = fr.constatsUi;

/** Constats soumis à l'audité (le serveur ne renvoie que les constats soumis ou validés). */
export function ConstatsAuditePage() {
  const { id } = useParams();
  const findings = useFindings({ mission: id });
  const [toAnswer, setToAnswer] = useState(false);

  let body;
  if (findings.isPending) {
    body = <p role="status">{fr.common.loading}</p>;
  } else if (findings.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else {
    const rows = toAnswer
      ? findings.data.results.filter(
          (c) => c.actions_possibles.includes("REPONDRE") && !c.reponse_cycle_courant,
        )
      : findings.data.results;
    body =
      rows.length === 0 ? (
        <p className="text-sm text-text-muted">
          {toAnswer && findings.data.results.length > 0 ? t.auditeeNothingToAnswer : t.auditeeEmpty}
        </p>
      ) : (
        <ConstatsTable missionId={id ?? ""} constats={rows} />
      );
  }

  return (
    <section aria-labelledby="constats-audite-title" className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="constats-audite-title" className="text-lg font-semibold">
          {fr.missions.tabConstats}
        </h2>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={toAnswer}
            onChange={(e) => setToAnswer(e.target.checked)}
          />
          {t.auditeeFilter}
        </label>
      </div>
      {id && <ResultsAgreementCard missionId={id} />}
      {body}
    </section>
  );
}
