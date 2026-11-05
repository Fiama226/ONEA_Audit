import { Copy, TriangleAlert } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";

const t = fr.utilisateurs.motDePasse;

/**
 * Affichage unique d'un mot de passe temporaire : il n'existe que dans l'état du composant
 * parent (jamais en cache), et disparaît du DOM avec la fenêtre qui le montre.
 */
export function TemporaryPassword({ value }: { value: string }) {
  const id = useId();
  const [copy, setCopy] = useState<"idle" | "done" | "failed">("idle");

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(value);
      setCopy("done");
    } catch {
      setCopy("failed");
    }
  }

  return (
    <div className="grid gap-2">
      <p id={`${id}-label`} className="text-sm font-medium">
        {t.label}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <output
          aria-labelledby={`${id}-label`}
          aria-describedby={`${id}-warning`}
          className="rounded-md border border-border bg-surface-subtle px-3 py-2 font-mono text-base tracking-wide select-all"
        >
          {value}
        </output>
        <Button type="button" variant="outline" onClick={() => void copyToClipboard()}>
          <Copy aria-hidden />
          {t.copy}
        </Button>
      </div>
      <p
        id={`${id}-warning`}
        className="flex gap-2 rounded-md border border-warning/50 p-3 text-sm text-warning-text"
      >
        <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>{t.warning}</span>
      </p>
      <p role="status" className="text-sm text-success-text">
        {copy === "done" ? t.copied : ""}
      </p>
      {copy === "failed" && (
        <p role="alert" className="text-sm text-destructive">
          {t.copyFailed}
        </p>
      )}
    </div>
  );
}
