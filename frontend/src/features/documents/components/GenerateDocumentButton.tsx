import { useId } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useGenerateDocument } from "../api";
import type { DocumentDisponible } from "../types";

/** « Générer » / « Régénérer » ; l'état d'autorisation vient du serveur (`peut_generer`, `raison`). */
export function GenerateDocumentButton({ disponible }: { disponible: DocumentDisponible }) {
  const helpId = useId();
  const generate = useGenerateDocument();
  const disabled = !disponible.peut_generer || disponible.en_cours || generate.isPending;
  const help = !disponible.peut_generer ? disponible.raison : null;
  const error = generate.error
    ? isApiError(generate.error)
      ? generate.error.detail
      : fr.errors.generic
    : null;

  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        type="button"
        size="sm"
        disabled={disabled}
        aria-describedby={help ? helpId : undefined}
        onClick={() =>
          generate.mutate({ type_document: disponible.type_document, objet: disponible.objet_id })
        }
      >
        {disponible.en_cours || generate.isPending
          ? fr.documents.generating
          : disponible.document
            ? fr.documents.regenerate
            : fr.documents.generate}
      </Button>
      {help ? (
        <span id={helpId} className="text-xs text-text-muted">
          {help}
        </span>
      ) : null}
      {error ? (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
