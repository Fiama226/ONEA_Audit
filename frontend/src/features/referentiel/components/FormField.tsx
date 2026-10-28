import { useId, type ReactNode } from "react";
import { Label } from "@/components/ui/label";

type Props = {
  label: string;
  error?: string;
  help?: string;
  children: (props: {
    id: string;
    "aria-invalid": boolean;
    "aria-describedby": string | undefined;
  }) => ReactNode;
};

/** Champ de formulaire accessible : libellé, aide et message d'erreur reliés au contrôle. */
export function FormField({ label, error, help, children }: Props) {
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
        <p id={errorId} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

export const SELECT_CLASS =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 aria-invalid:border-destructive disabled:cursor-not-allowed disabled:opacity-50";

export const ALERT_CLASS = "rounded-md border border-destructive/40 p-3 text-sm text-destructive";
