import { useState } from "react";
import { isApiError } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { ALERT_CLASS } from "@/features/referentiel/components/FormField";
import { fr } from "@/i18n/fr";
import { useAccountAction } from "../api";
import type { CompteUtilisateur } from "../types";

const t = fr.utilisateurs.fiche;

/** État de la synchronisation du compte avec Keycloak, et relance manuelle en cas d'échec. */
export function KeycloakSyncNotice({ account }: { account: CompteUtilisateur }) {
  const action = useAccountAction();
  const [retryError, setRetryError] = useState<string | null>(null);
  const sync = account.keycloak_sync;

  async function retry() {
    setRetryError(null);
    try {
      await action.mutateAsync({ id: account.id, action: "retry-keycloak-sync" });
    } catch (e) {
      setRetryError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  if (!account.keycloak_lie) {
    return <p className="text-sm text-text-muted">{t.syncNotLinked}</p>;
  }

  return (
    <div className="grid gap-2">
      {sync.statut === "A_JOUR" && (
        <p className="text-sm">{account.is_active ? t.syncActive : t.syncInactive}</p>
      )}
      {sync.statut === "EN_ATTENTE" && <p className="text-sm">{t.syncPending}</p>}
      {sync.statut === "ECHEC" && (
        <div role="alert" className={`grid gap-1 ${ALERT_CLASS}`}>
          <p>
            {t.syncFailed}
            {sync.erreur}
            {account.is_active ? t.accessRestored : t.accessCut}
          </p>
          {sync.manuel && <p>{t.syncManual}</p>}
        </div>
      )}
      {retryError && (
        <p role="alert" className={ALERT_CLASS}>
          {retryError}
        </p>
      )}
      {account.actions.relancer_synchro_keycloak && sync.statut !== "A_JOUR" && (
        <div className="print:hidden">
          <Button
            type="button"
            variant="outline"
            disabled={action.isPending}
            onClick={() => void retry()}
          >
            {action.isPending ? t.syncRetrying : t.syncRetry}
          </Button>
        </div>
      )}
    </div>
  );
}
