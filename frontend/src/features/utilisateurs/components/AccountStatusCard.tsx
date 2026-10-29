import { useRef, useState } from "react";
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
  const by = account.desactive_par ? `${t.deactivatedBy}${account.desactive_par.nom_complet}` : "";
  const reason = account.motif_desactivation
    ? `${t.reasonSeparator}${account.motif_desactivation}`
    : "";
  return `${t.deactivatedOn}${formatDateTime(account.desactive_le)}${by}${reason}`;
}

/** Statut d'accès du compte, synchronisation Keycloak, désactivation et réactivation. */
export function AccountStatusCard({ account }: { account: CompteUtilisateur }) {
  const [dialog, setDialog] = useState<"deactivate" | "reactivate" | null>(null);
  const [notice, setNotice] = useState("");
  const noticeRef = useRef<HTMLParagraphElement>(null);
  const focusNotice = useRef(false);

  function open(next: "deactivate" | "reactivate") {
    setNotice("");
    setDialog(next);
  }

  function done(message: string) {
    focusNotice.current = true;
    setDialog(null);
    setNotice(message);
  }

  /** Le bouton déclencheur a disparu : le focus va au message de résultat plutôt qu'à <body>. */
  function onCloseAutoFocus(event: Event) {
    if (!focusNotice.current) return;
    focusNotice.current = false;
    event.preventDefault();
    noticeRef.current?.focus();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.accountTitle}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm">
        <p className="font-medium">{statusText(account)}</p>
        <p ref={noticeRef} tabIndex={-1} role="status" className="text-success-text outline-none">
          {notice}
        </p>
        <KeycloakSyncNotice
          key={`${account.keycloak_sync.statut}-${account.is_active}`}
          account={account}
        />
        <div className="flex flex-wrap gap-2 print:hidden">
          {account.actions.desactiver && (
            <Button type="button" variant="destructive" onClick={() => open("deactivate")}>
              {t.deactivate}
            </Button>
          )}
          {account.actions.reactiver && (
            <Button type="button" variant="outline" onClick={() => open("reactivate")}>
              {t.reactivate}
            </Button>
          )}
        </div>
      </CardContent>
      <DeactivateDialog
        account={account}
        open={dialog === "deactivate"}
        onOpenChange={(o) => !o && setDialog(null)}
        onCloseAutoFocus={onCloseAutoFocus}
        onDone={() => done(t.deactivated)}
      />
      <ReactivateDialog
        account={account}
        open={dialog === "reactivate"}
        onOpenChange={(o) => !o && setDialog(null)}
        onCloseAutoFocus={onCloseAutoFocus}
        onDone={() => done(t.reactivated)}
      />
    </Card>
  );
}
