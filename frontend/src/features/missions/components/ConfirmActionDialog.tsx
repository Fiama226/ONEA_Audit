import { useId, useState } from "react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ALERT_CLASS } from "@/components/form/FormField";
import { isApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Texte que l'utilisateur doit lire et confirmer explicitement. */
  text: string;
  confirmLabel: string;
  /** Lève une ApiError en cas de refus ; la boîte reste alors ouverte. */
  onConfirm: () => Promise<unknown>;
};

/** Confirmation explicite : le bouton reste inactif tant que « Je confirme » n'est pas coché. */
export function ConfirmActionDialog({
  open,
  onOpenChange,
  title,
  text,
  confirmLabel,
  onConfirm,
}: Props) {
  const id = useId();
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function change(next: boolean) {
    if (pending) return;
    if (!next) {
      setChecked(false);
      setError(null);
    }
    onOpenChange(next);
  }

  async function confirm() {
    setPending(true);
    setError(null);
    try {
      await onConfirm();
      setPending(false);
      setChecked(false);
      onOpenChange(false);
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
      setPending(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={change}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{text}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex items-center gap-2">
          <Checkbox
            id={id}
            checked={checked}
            onCheckedChange={(value) => setChecked(value === true)}
          />
          <Label htmlFor={id}>{fr.missions.confirmCheckbox}</Label>
        </div>
        {error && (
          <p role="alert" className={ALERT_CLASS}>
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>{fr.common.cancel}</AlertDialogCancel>
          <Button type="button" disabled={!checked || pending} onClick={() => void confirm()}>
            {confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
