import { useState, type ReactNode } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";

const t = fr.communication;

/** Confirmation renvoyée par le serveur : date et empreinte affichées après succès. */
export type ConfirmationRecue = { confirme_le: string; empreinte: string };

type Props = {
  title: string;
  /** Texte légal fourni par le serveur, affiché tel quel. */
  texte: string;
  confirmLabel: string;
  onConfirm: () => Promise<ConfirmationRecue | void>;
  /** Déclencheur (bouton) ; sans lui, le dialogue est contrôlé par `open`. */
  children?: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

/**
 * Dialogue de confirmation d'un texte légal (réponse, acceptation, engagement, validation).
 * La case « Je confirme » n'est jamais pré-cochée et l'envoi est bloqué sans elle.
 */
export function ConfirmationTextDialog({ children, open, onOpenChange, ...rest }: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      {children && <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>}
      <AlertDialogContent>
        <ConfirmationBody {...rest} />
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ConfirmationBody({
  title,
  texte,
  confirmLabel,
  onConfirm,
}: Pick<Props, "title" | "texte" | "confirmLabel" | "onConfirm">) {
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState<ConfirmationRecue | "ok" | null>(null);

  async function submit() {
    setError(null);
    setPending(true);
    try {
      setDone((await onConfirm()) ?? "ok");
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : t.confirmError);
    } finally {
      setPending(false);
    }
  }

  if (done) {
    let message: string = t.confirmOk;
    if (done !== "ok") {
      const [date = "", heure = ""] = formatDateTime(done.confirme_le).split(" ");
      message = t.confirmDone
        .replace("{date}", date)
        .replace("{heure}", heure)
        .replace("{empreinte}", done.empreinte);
    }
    return (
      <>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription role="status">{message}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{fr.common.close}</AlertDialogCancel>
        </AlertDialogFooter>
      </>
    );
  }

  return (
    <div className="grid gap-4">
      <AlertDialogHeader>
        <AlertDialogTitle>{title}</AlertDialogTitle>
        <AlertDialogDescription className="sr-only">{title}</AlertDialogDescription>
      </AlertDialogHeader>
      <p className="rounded-md border border-border p-3 text-sm whitespace-pre-line">{texte}</p>
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      <label className="flex items-center gap-2 text-sm font-medium">
        <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
        {t.confirmCheckbox}
      </label>
      <AlertDialogFooter>
        <AlertDialogCancel type="button">{fr.common.cancel}</AlertDialogCancel>
        <Button type="button" disabled={!checked || pending} onClick={() => void submit()}>
          {pending ? t.confirmPending : confirmLabel}
        </Button>
      </AlertDialogFooter>
    </div>
  );
}
