import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { useReportAction } from "../api";
import type { Rapport } from "../types";
import { ValidationPanel } from "./ValidationPanel";

const t = fr.rapportFinal;

/** Actions du rapport selon `actions_possibles` : soumission (chef), puis validation (RAI). */
export function ReportActions({ rapport }: { rapport: Rapport }) {
  const [submitting, setSubmitting] = useState(false);
  const action = useReportAction();
  const canSubmit = rapport.actions_possibles.includes("SOUMETTRE");

  return (
    <div className="grid gap-3 print:hidden">
      {canSubmit && (
        <div>
          <Button type="button" onClick={() => setSubmitting(true)}>
            {t.submit}
          </Button>
          <ConfirmActionDialog
            open={submitting}
            onOpenChange={setSubmitting}
            title={t.submitTitle}
            text={t.submitText}
            confirmLabel={t.submitConfirm}
            onConfirm={() =>
              action.mutateAsync({ id: rapport.id, missionId: rapport.mission, action: "submit" })
            }
          />
        </div>
      )}
      {rapport.statut === "SOUMIS" && !canSubmit && <ValidationPanelOrWaiting rapport={rapport} />}
    </div>
  );
}

function ValidationPanelOrWaiting({ rapport }: { rapport: Rapport }) {
  const rai =
    rapport.actions_possibles.includes("VALIDER") || rapport.actions_possibles.includes("RENVOYER");
  return rai ? (
    <ValidationPanel rapport={rapport} />
  ) : (
    <p role="status" className="text-sm text-text-muted">
      {t.awaitingRai}
    </p>
  );
}
