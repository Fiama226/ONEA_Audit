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
import { isApiError, type ApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Texte que l'utilisateur doit lire et confirmer explicitement. */
  text: string;
  confirmLabel: string;
  /** Faux : pas de case « Je confirme » (actions réversibles) ; la boîte sert alors à afficher les refus. */
  requireCheck?: boolean;
  /** Lève une ApiError en cas de refus ; la boîte reste alors ouverte. */
  onConfirm: () => Promise<unknown>;
};

/** Message général puis messages par champ (ex. champs manquants), sans doublon. Un champ connu
 * est nommé (« Entités auditées : … ») : sinon des champs différents affichent le même texte. */
function errorLines(e: ApiError): string[] {
  const lines = [e.detail];
  for (const [field, messages] of Object.entries(e.errors)) {
    const label = (fr.missions.fieldLabels as Record<string, string>)[field];
    for (const message of messages) {
      const line = label ? `${label} : ${message}` : message;
      if (!lines.includes(line)) lines.push(line);
    }
  }
  return lines;
}

/** Confirmation explicite : le bouton reste inactif tant que « Je confirme » n'est pas coché. */
export function ConfirmActionDialog({
  open,
  onOpenChange,
  title,
  text,
  confirmLabel,
  requireCheck = true,
  onConfirm,
}: Props) {
  const id = useId();
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string[] | null>(null);
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
      setError(isApiError(e) ? errorLines(e) : [fr.errors.generic]);
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
        {requireCheck && (
          <div className="flex items-center gap-2">
            <Checkbox
              id={id}
              checked={checked}
              onCheckedChange={(value) => setChecked(value === true)}
            />
            <Label htmlFor={id}>{fr.missions.confirmCheckbox}</Label>
          </div>
        )}
        {error && (
          <div role="alert" className={ALERT_CLASS}>
            <p>{error[0]}</p>
            {error.length > 1 && (
              <ul className="mt-1 list-disc pl-5">
                {error.slice(1).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>{fr.common.cancel}</AlertDialogCancel>
          <Button
            type="button"
            disabled={(requireCheck && !checked) || pending}
            onClick={() => void confirm()}
          >
            {confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
