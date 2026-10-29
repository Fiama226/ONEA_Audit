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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ALERT_CLASS } from "@/components/form/FormField";
import { isApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel: string;
  /** Lève une ApiError en cas de refus (422 : motif invalide) ; la boîte reste alors ouverte. */
  onSubmit: (motif: string) => Promise<unknown>;
};

/** Boîte de dialogue demandant un motif obligatoire avant une action. */
export function MotifDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onSubmit,
}: Props) {
  const id = useId();
  const [motif, setMotif] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function reset() {
    setMotif("");
    setError(null);
  }

  function change(next: boolean) {
    if (pending) return;
    if (!next) reset();
    onOpenChange(next);
  }

  async function submit() {
    const trimmed = motif.trim();
    if (!trimmed) {
      setError(fr.missions.motifRequired);
      return;
    }
    setPending(true);
    setError(null);
    try {
      await onSubmit(trimmed);
      setPending(false);
      reset();
      onOpenChange(false);
    } catch (e) {
      // Le serveur recopie souvent l'erreur du champ dans `detail` : ne montrer que l'un des deux.
      setError(isApiError(e) ? (e.errors.motif?.join(" ") ?? e.detail) : fr.errors.generic);
      setPending(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={change}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        <div className="grid gap-1.5">
          <Label htmlFor={id}>{fr.missions.motifLabel}</Label>
          <Textarea
            id={id}
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            aria-invalid={error !== null}
            required
            rows={4}
          />
        </div>
        {error && (
          <p role="alert" className={ALERT_CLASS}>
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>{fr.common.cancel}</AlertDialogCancel>
          <Button type="button" disabled={pending} onClick={() => void submit()}>
            {confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
