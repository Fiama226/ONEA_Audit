import { useEffect, useId, useRef, useState } from "react";
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
import { ALERT_CLASS } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { useResetPassword } from "../api";
import type { CompteUtilisateur, MotDePasseTemporaire } from "../types";
import { TemporaryPassword } from "./TemporaryPassword";

const t = fr.utilisateurs.securite;

type Props = {
  account: CompteUtilisateur;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Confirmation, puis nouveau mot de passe temporaire affiché une fois s'il n'est pas parti par courriel. */
export function ResetPasswordDialog({ account, open, onOpenChange }: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <ResetPasswordBody account={account} onClose={() => onOpenChange(false)} />
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** Démonté à la fermeture : le mot de passe affiché disparaît avec lui. */
function ResetPasswordBody({
  account,
  onClose,
}: {
  account: CompteUtilisateur;
  onClose: () => void;
}) {
  const mutation = useResetPassword();
  const hasEmail = account.email !== "";
  const [sendEmail, setSendEmail] = useState(hasEmail);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MotDePasseTemporaire | null>(null);
  const helpId = useId();

  async function confirm() {
    setError(null);
    try {
      const response = await mutation.mutateAsync({ id: account.id, sendEmail });
      // Le cache des mutations ne garde pas la réponse (et donc pas le mot de passe).
      mutation.reset();
      setResult(response);
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <>
      <AlertDialogHeader>
        <AlertDialogTitle>{`${t.resetTitle}${account.nom_complet} ?`}</AlertDialogTitle>
        <AlertDialogDescription>{t.resetText}</AlertDialogDescription>
      </AlertDialogHeader>
      {result ? (
        <ResetResult result={result} onClose={onClose} />
      ) : (
        <>
          {error && (
            <p role="alert" className={ALERT_CLASS}>
              {error}
            </p>
          )}
          <div className="grid gap-1">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={sendEmail}
                disabled={!hasEmail || mutation.isPending}
                aria-describedby={hasEmail ? undefined : helpId}
                onChange={(e) => setSendEmail(e.target.checked)}
              />
              {t.resetSendEmail}
            </label>
            {!hasEmail && (
              <p id={helpId} className="text-xs text-text-muted">
                {t.resetNoEmail}
              </p>
            )}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel type="button" disabled={mutation.isPending}>
              {fr.common.cancel}
            </AlertDialogCancel>
            <Button type="button" disabled={mutation.isPending} onClick={() => void confirm()}>
              {mutation.isPending ? t.resetting : t.resetConfirm}
            </Button>
          </AlertDialogFooter>
        </>
      )}
    </>
  );
}

function ResetResult({ result, onClose }: { result: MotDePasseTemporaire; onClose: () => void }) {
  const statusRef = useRef<HTMLParagraphElement>(null);
  // Les boutons de confirmation ont disparu : le focus va au résultat.
  useEffect(() => {
    statusRef.current?.focus();
  }, []);
  return (
    <div className="grid gap-4">
      <p ref={statusRef} tabIndex={-1} className="text-sm font-medium outline-none">
        {result.courriel_envoye
          ? `${t.resetDone} ${t.resetEmailed}${result.compte.email}.`
          : `${t.resetDone} ${fr.utilisateurs.creation.notEmailed}`}
      </p>
      {result.mot_de_passe_temporaire && (
        <TemporaryPassword value={result.mot_de_passe_temporaire} />
      )}
      <AlertDialogFooter>
        <Button type="button" onClick={onClose}>
          {t.close}
        </Button>
      </AlertDialogFooter>
    </div>
  );
}
