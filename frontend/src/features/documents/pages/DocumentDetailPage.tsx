import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { isApiError } from "@/api/errors";
import { useRole } from "@/auth/useRole";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { documentKeys, useDocument, useVersion } from "../api";
import { ConsultationsTable } from "../components/ConsultationsTable";
import { DocumentStatusBadge } from "../components/DocumentStatusBadge";
import { DownloadButtons } from "../components/DownloadButtons";
import { VersionHistory } from "../components/VersionHistory";
import { isInProgress } from "../labels";

const t = fr.documentsRegistre;

export function DocumentDetailPage() {
  const { id } = useParams();
  const { is } = useRole();
  const client = useQueryClient();
  const document = useDocument(id);
  const latestId = document.data?.derniere_version?.id;
  // Interrogation périodique (budget de 3 minutes) tant que la dernière version est en traitement.
  const version = useVersion(latestId);
  const polled = version.data;

  // Fin d'un traitement : l'historique des versions est relu pour refléter l'état final.
  // Seule une transition « en cours » -> terminé relit le document, pas le premier chargement.
  const previous = useRef<{ id: string; inProgress: boolean } | null>(null);
  const polledId = polled?.id;
  const polledStatut = polled?.statut;
  const polledPdf = polled?.statut_pdf;
  useEffect(() => {
    if (!polledId || !polledStatut || !polledPdf) return;
    const inProgress = isInProgress({ statut: polledStatut, statut_pdf: polledPdf });
    const before = previous.current;
    previous.current = { id: polledId, inProgress };
    if (before?.id === polledId && before.inProgress && !inProgress && id) {
      void client.invalidateQueries({ queryKey: documentKeys.document(id) });
    }
  }, [polledId, polledStatut, polledPdf, id, client]);

  if (document.isError) {
    const notFound = isApiError(document.error) && document.error.status === 404;
    return (
      <div className="grid gap-4">
        <h1 className="text-2xl font-semibold tracking-[-0.012em]">{t.detailTitle}</h1>
        <div role="alert" className={ALERT_CLASS}>
          <p>{notFound ? t.notFound : t.detailLoadError}</p>
          {notFound ? null : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => void document.refetch()}
            >
              {fr.common.retry}
            </Button>
          )}
        </div>
        <Link to="/documents" className="text-sm font-medium text-primary hover:underline">
          {t.backToList}
        </Link>
      </div>
    );
  }
  if (!document.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }

  const doc = document.data;
  const current = polled ?? doc.derniere_version;

  return (
    <div className="grid gap-6">
      <header className="grid gap-2">
        <h1 className="text-2xl font-semibold tracking-[-0.012em] [overflow-wrap:anywhere]">
          {doc.numero}
        </h1>
        <dl className="grid gap-x-8 gap-y-1 text-sm [overflow-wrap:anywhere] sm:grid-cols-[auto_1fr]">
          <dt className="text-text-muted">{t.type}</dt>
          <dd>{doc.type_document_libelle}</dd>
          <dt className="text-text-muted">{t.mission}</dt>
          <dd>
            <Link
              to={`/missions/${doc.mission.id}`}
              className="font-medium text-primary underline-offset-[3px] hover:underline"
            >
              {doc.mission.reference
                ? `${doc.mission.reference} — ${doc.mission.titre}`
                : doc.mission.titre}
            </Link>
          </dd>
          {current ? (
            <>
              <dt className="text-text-muted">{t.latestVersion}</dt>
              <dd className="flex flex-wrap items-center gap-2">
                <span>{`v${current.numero_version}`}</span>
                <DocumentStatusBadge version={current} />
              </dd>
            </>
          ) : null}
        </dl>
        {current ? (
          <div className="print:hidden">
            <DownloadButtons version={polled ?? current} />
          </div>
        ) : null}
        {version.timeoutError ? (
          <div role="alert" className={`${ALERT_CLASS} print:hidden`}>
            <p>{version.timeoutError.detail}</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => version.restartPolling()}
            >
              {fr.common.retry}
            </Button>
          </div>
        ) : null}
      </header>

      <section aria-labelledby="doc-versions" className="grid gap-2">
        <h2 id="doc-versions" className="text-lg font-semibold">
          {t.versionsHeading}
        </h2>
        <VersionHistory document={doc} />
      </section>

      {is("RAI") && latestId ? (
        <section aria-labelledby="doc-consultations" className="grid gap-2">
          <h2 id="doc-consultations" className="text-lg font-semibold">
            {t.consultationsHeading}
          </h2>
          <ConsultationsTable versionId={latestId} />
        </section>
      ) : null}

      <div className="print:hidden">
        <Link to="/documents" className="text-sm font-medium text-primary hover:underline">
          {t.backToList}
        </Link>
      </div>
    </div>
  );
}
