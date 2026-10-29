import { Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";

/** Empreinte abrégée (8 premiers + 4 derniers caractères) ; valeur complète en infobulle et copiable. */
export function HashDisplay({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-text-muted">—</span>;
  const short = value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-1">
      <code title={value} className="font-mono text-xs">
        {short}
      </code>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-6"
        aria-label={fr.documents.copyHash}
        onClick={() => void copy()}
      >
        <Copy aria-hidden="true" className="size-3.5" />
      </Button>
      <span role="status" className="sr-only">
        {copied ? fr.documents.hashCopied : ""}
      </span>
    </span>
  );
}
