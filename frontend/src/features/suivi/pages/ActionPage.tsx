import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { useFollowUpAction } from "../api";
import { ActionHeader } from "../components/ActionHeader";
import { ActionTimeline } from "../components/ActionTimeline";
import { ActionTransitions } from "../components/ActionTransitions";
import { EvidencePanel } from "../components/EvidencePanel";
import { ExtensionPanel } from "../components/ExtensionPanel";
import { ResponsibleDialog } from "../components/ResponsibleDialog";

const t = fr.suiviRegistre;

/** Suivi d'une action : synthèse, transitions, preuves, report et chronologie. */
export function ActionPage() {
  const { id } = useParams();
  const query = useFollowUpAction(id);
  const [responsibleOpen, setResponsibleOpen] = useState(false);
  const action = query.data;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-[-0.012em]">{fr.suivi.actionTitle}</h1>
        <Link to="/recommandations?vue=actions" className="text-sm text-primary hover:underline">
          {t.backToRegister}
        </Link>
      </div>
      {query.isLoading ? (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      ) : !action ? (
        <p role="alert" className={ALERT_CLASS}>
          {isApiError(query.error) && query.error.status === 404
            ? t.actionNotFound
            : t.actionLoadError}
        </p>
      ) : (
        <div className="grid gap-5">
          <ActionHeader
            action={action}
            onChangeResponsible={
              action.actions_possibles.includes("CHANGER_RESPONSABLE")
                ? () => setResponsibleOpen(true)
                : undefined
            }
          />
          <ActionTransitions action={action} />
          <EvidencePanel action={action} />
          <ExtensionPanel action={action} />
          <ActionTimeline
            actionId={action.id}
            missionId={action.mission.id}
            canComment={action.actions_possibles.includes("COMMENTER")}
          />
          <ResponsibleDialog
            action={action}
            open={responsibleOpen}
            onOpenChange={setResponsibleOpen}
          />
        </div>
      )}
    </>
  );
}
