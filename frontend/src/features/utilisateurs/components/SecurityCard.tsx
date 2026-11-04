import { useRef, useState } from "react";
import { isApiError } from "@/api/errors";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ALERT_CLASS } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useAccountAction } from "../api";
import type { CompteUtilisateur } from "../types";
import { ResetPasswordDialog } from "./ResetPasswordDialog";

const t = fr.utilisateurs.securite;

/**
 * Connexion et mot de passe d'un agent : état (mot de passe temporaire, blocage, code de
 * connexion), réinitialisation du mot de passe et désactivation du code de connexion. Les
 * boutons suivent `account.actions` (droit « réinitialiser », jamais sur son propre compte).
 */
export function SecurityCard({ account }: { account: CompteUtilisateur }) {
  const [dialog, setDialog] = useState<"reset" | "otp" | null>(null);
  const [notice, setNotice] = useState("");
  const noticeRef = useRef<HTMLParagraphElement>(null);
  const focusNotice = useRef(false);
  const { actions } = account;

  function open(next: "reset" | "otp") {
    setNotice("");
    setDialog(next);
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
        <CardTitle>{t.title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <ul className="grid gap-1">
          {account.doit_changer_mot_de_passe && <li>{t.mustChange}</li>}
          {account.doit_changer_mot_de_passe && account.mot_de_passe_expire_le && (
            <li>{`${t.expiresOn}${formatDateTime(account.mot_de_passe_expire_le)}.`}</li>
          )}
          {account.verrouille_jusqu_a && (
            <li className="text-warning-text">
              {`${t.lockedUntil}${formatDateTime(account.verrouille_jusqu_a)}.`}
            </li>
          )}
          <li>{account.otp_connexion_actif ? t.otpOn : t.otpOff}</li>
        </ul>
        <p ref={noticeRef} tabIndex={-1} role="status" className="text-success-text outline-none">
          {notice}
        </p>
        {(actions.reinitialiser_mot_de_passe || actions.desactiver_otp) && (
          <div className="flex flex-wrap gap-2 print:hidden">
            {actions.reinitialiser_mot_de_passe && (
              <Button type="button" variant="outline" onClick={() => open("reset")}>
                {t.reset}
              </Button>
            )}
            {actions.desactiver_otp && (
              <Button type="button" variant="outline" onClick={() => open("otp")}>
                {t.disableOtp}
              </Button>
            )}
          </div>
        )}
      </CardContent>
      {dialog === "reset" && (
        <ResetPasswordDialog account={account} open onOpenChange={(o) => !o && setDialog(null)} />
      )}
      <AlertDialog open={dialog === "otp"} onOpenChange={(o) => !o && setDialog(null)}>
        <AlertDialogContent onCloseAutoFocus={onCloseAutoFocus}>
          <DisableOtpBody
            account={account}
            onDone={() => {
              focusNotice.current = true;
              setDialog(null);
              setNotice(t.otpDisabled);
            }}
          />
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}

function DisableOtpBody({ account, onDone }: { account: CompteUtilisateur; onDone: () => void }) {
  const action = useAccountAction();
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setError(null);
    try {
      await action.mutateAsync({ id: account.id, action: "disable-otp" });
      onDone();
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <>
      <AlertDialogHeader>
        <AlertDialogTitle>{`${t.disableOtpTitle}${account.nom_complet} ?`}</AlertDialogTitle>
        <AlertDialogDescription>{t.disableOtpText}</AlertDialogDescription>
      </AlertDialogHeader>
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      <AlertDialogFooter>
        <AlertDialogCancel disabled={action.isPending}>{fr.common.cancel}</AlertDialogCancel>
        <Button type="button" disabled={action.isPending} onClick={() => void confirm()}>
          {t.disableOtpConfirm}
        </Button>
      </AlertDialogFooter>
    </>
  );
}
