import { useState } from "react";
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
import { useAccountAction } from "../api";
import type { CompteUtilisateur } from "../types";

const t = fr.utilisateurs.fiche;

type Props = {
  account: CompteUtilisateur;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
  onCloseAutoFocus?: (event: Event) => void;
};

export function ReactivateDialog({ account, open, onOpenChange, onDone, onCloseAutoFocus }: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent onCloseAutoFocus={onCloseAutoFocus}>
        <ReactivateBody account={account} onDone={onDone} />
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** Contenu démonté à la fermeture : l'erreur d'une tentative précédente ne survit pas. */
function ReactivateBody({ account, onDone }: Pick<Props, "account" | "onDone">) {
  const action = useAccountAction();
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setError(null);
    try {
      await action.mutateAsync({ id: account.id, action: "reactivate" });
      onDone();
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <>
      <AlertDialogHeader>
        <AlertDialogTitle>{`${t.reactivateTitle}${account.nom_complet} ?`}</AlertDialogTitle>
        <AlertDialogDescription>{t.reactivateText}</AlertDialogDescription>
      </AlertDialogHeader>
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      <AlertDialogFooter>
        <AlertDialogCancel disabled={action.isPending}>{fr.common.cancel}</AlertDialogCancel>
        <Button type="button" disabled={action.isPending} onClick={() => void confirm()}>
          {t.reactivateConfirm}
        </Button>
      </AlertDialogFooter>
    </>
  );
}
