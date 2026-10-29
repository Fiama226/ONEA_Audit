import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import type { CompteUtilisateur } from "../types";
import { DeactivateDialog } from "./DeactivateDialog";
import { KeycloakSyncNotice } from "./KeycloakSyncNotice";
import { ReactivateDialog } from "./ReactivateDialog";

const t = fr.utilisateurs.fiche;

function statusText(account: CompteUtilisateur): string {
  if (account.is_active) return t.accountActive;
  if (!account.desactive_le) return t.accountInactive;
  const by = account.desactive_par?.nom_complet ?? "";
  return `${t.deactivatedOn}${formatDateTime(account.desactive_le)}${t.deactivatedBy}${by}${t.reasonSeparator}${account.motif_desactivation}`;
}

/** Statut d'accès du compte, synchronisation Keycloak, désactivation et réactivation. */
export function AccountStatusCard({ account }: { account: CompteUtilisateur }) {
  const [dialog, setDialog] = useState<"deactivate" | "reactivate" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.accountTitle}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm">
        <p className="font-medium">{statusText(account)}</p>
        {notice && (
          <p role="status" className="text-success-text">
            {notice}
          </p>
        )}
        <KeycloakSyncNotice account={account} />
        <div className="flex flex-wrap gap-2 print:hidden">
          {account.actions.desactiver && (
            <Button type="button" variant="destructive" onClick={() => setDialog("deactivate")}>
              {t.deactivate}
            </Button>
          )}
          {account.actions.reactiver && (
            <Button type="button" variant="outline" onClick={() => setDialog("reactivate")}>
              {t.reactivate}
            </Button>
          )}
        </div>
      </CardContent>
      <DeactivateDialog
        account={account}
        open={dialog === "deactivate"}
        onOpenChange={(o) => !o && setDialog(null)}
        onDone={() => {
          setDialog(null);
          setNotice(t.deactivated);
        }}
      />
      <ReactivateDialog
        account={account}
        open={dialog === "reactivate"}
        onOpenChange={(o) => !o && setDialog(null)}
        onDone={() => {
          setDialog(null);
          setNotice(t.reactivated);
        }}
      />
    </Card>
  );
}
