import { Badge } from "@/components/ui/badge";
import { STATUT_GENERATION_LABELS, STATUT_PDF_LABELS } from "../labels";
import type { VersionStatus } from "../types";

/** Statut de génération ; le statut du PDF s'ajoute seulement s'il est en cours ou en échec. */
export function DocumentStatusBadge({ version }: { version: VersionStatus }) {
  const variant =
    version.statut === "ECHEC"
      ? "destructive"
      : version.statut === "PRETE"
        ? "default"
        : "secondary";
  const pdfNote = version.statut_pdf === "EN_COURS" || version.statut_pdf === "ECHEC";
  return (
    // role="status" (aria-live polite) : le passage « en cours » -> « Prête » / « Échec » est annoncé.
    <span role="status" className="inline-flex flex-wrap items-center gap-1">
      <Badge variant={variant}>{STATUT_GENERATION_LABELS[version.statut]}</Badge>
      {version.statut === "PRETE" && pdfNote ? (
        <Badge variant={version.statut_pdf === "ECHEC" ? "destructive" : "secondary"}>
          {STATUT_PDF_LABELS[version.statut_pdf]}
        </Badge>
      ) : null}
    </span>
  );
}
