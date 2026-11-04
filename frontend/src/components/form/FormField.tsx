import { useId, type ReactNode } from "react";
import { Label } from "@/components/ui/label";

type Props = {
  label: string;
  error?: string;
  help?: string;
  /**
   * Annonce l'erreur (role="alert") : pour un refus du serveur affiché sur un champ qui a déjà
   * le focus (envoi par Entrée), que le déplacement du focus ne suffit pas à signaler.
   */
  announceError?: boolean;
  children: (props: {
    id: string;
    "aria-invalid": boolean;
    "aria-describedby": string | undefined;
  }) => ReactNode;
};

/** Champ de formulaire accessible : libellé, aide et message d'erreur reliés au contrôle. */
export function FormField({ label, error, help, announceError = false, children }: Props) {
  const id = useId();
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;
  const describedBy = [help ? helpId : null, error ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children({
        id,
        "aria-invalid": error !== undefined,
        "aria-describedby": describedBy || undefined,
      })}
      {help && (
        <p id={helpId} className="text-xs text-text-muted">
          {help}
        </p>
      )}
      {error && (
        <p
          id={errorId}
          role={announceError ? "alert" : undefined}
          className="text-sm text-destructive"
        >
          {error}
        </p>
      )}
    </div>
  );
}

export const ALERT_CLASS = "rounded-md border border-destructive/40 p-3 text-sm text-destructive";
