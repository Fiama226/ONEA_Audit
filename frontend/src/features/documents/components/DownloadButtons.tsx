import { useId, useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { downloadVersion, useRetryPdf } from "../api";
import type { DownloadableVersion, FormatFichier } from "../types";

/** Boutons de téléchargement Word et PDF d'une version, et relance du PDF si le serveur l'autorise. */
export function DownloadButtons({ version }: { version: DownloadableVersion }) {
  const reasonId = useId();
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const retry = useRetryPdf();
  const wordReady = version.statut === "PRETE";
  const pdfReady = wordReady && version.statut_pdf === "PRET";

  async function download(format: FormatFichier) {
    if (downloading) return;
    setError(null);
    setDownloading(true);
    try {
      await downloadVersion(version.id, format);
    } catch (e) {
      // 409 : empreinte du fichier stocké différente de l'empreinte enregistrée.
      setError(
        isApiError(e) && e.status === 409
          ? fr.documents.integrityError
          : isApiError(e)
            ? e.detail
            : fr.documents.downloadError,
      );
    } finally {
      setDownloading(false);
    }
  }

  const failure =
    error ??
    (retry.error ? (isApiError(retry.error) ? retry.error.detail : fr.errors.generic) : null);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!wordReady || downloading}
        onClick={() => void download("docx")}
      >
        {fr.documents.downloadWord}
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!pdfReady || downloading}
        aria-describedby={pdfReady ? undefined : reasonId}
        onClick={() => void download("pdf")}
      >
        {fr.documents.downloadPdf}
      </Button>
      {pdfReady ? null : (
        <span id={reasonId} className="text-xs text-text-muted">
          {fr.documents.pdfNotReady}
        </span>
      )}
      {version.peut_relancer_pdf ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={retry.isPending}
          onClick={() => retry.mutate(version.id)}
        >
          {fr.documents.retryPdf}
        </Button>
      ) : null}
      {failure ? (
        <p role="alert" className={ALERT_CLASS}>
          {failure}
        </p>
      ) : null}
    </div>
  );
}
