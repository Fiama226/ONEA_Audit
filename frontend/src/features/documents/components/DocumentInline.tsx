import { fr } from "@/i18n/fr";
import { useAvailableDocuments } from "../api";
import type { DocumentDisponible } from "../types";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { DownloadButtons } from "./DownloadButtons";
import { GenerateDocumentButton } from "./GenerateDocumentButton";

type Props = { typeDocument: string; objetId: string; missionId: string };

/** Ligne compacte d'un document de mission : libellé, numéro, version, statut, génération, téléchargement. */
export function DocumentInline({ typeDocument, objetId, missionId }: Props) {
  const available = useAvailableDocuments(missionId);
  if (available.isError) {
    return <p className="text-sm text-text-muted">{fr.documents.loadError}</p>;
  }
  if (!available.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const disponible = available.data.find(
    (d) => d.type_document === typeDocument && d.objet_id === objetId,
  );
  if (!disponible) {
    return <p className="text-sm text-text-muted">{fr.documents.noDocument}</p>;
  }
  return <DocumentRow disponible={disponible} timeoutError={available.timeoutError} />;
}

type RowProps = {
  disponible: DocumentDisponible;
  timeoutError?: { detail: string } | null;
};

/**
 * Une ligne de document. Le bouton « Générer » n'est proposé qu'à qui peut générer : sinon (audité,
 * par exemple) seule la raison est affichée, pour ne pas montrer une action interdite.
 */
export function DocumentRow({ disponible, timeoutError }: RowProps) {
  const version = disponible.document?.derniere_version ?? null;
  const canAct = disponible.peut_generer || disponible.en_cours;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
      <span className="font-medium">{disponible.libelle}</span>
      {disponible.document ? (
        <span className="text-text-muted">{disponible.document.numero}</span>
      ) : null}
      {version ? (
        <>
          <span>{`v${version.numero_version}`}</span>
          <DocumentStatusBadge version={version} />
        </>
      ) : (
        <span className="text-text-muted">{fr.documents.notGenerated}</span>
      )}
      {canAct ? (
        <GenerateDocumentButton disponible={disponible} />
      ) : disponible.raison ? (
        <span className="text-xs text-text-muted">{disponible.raison}</span>
      ) : null}
      {version ? <DownloadButtons version={version} /> : null}
      {timeoutError ? (
        <p role="alert" className="w-full text-xs text-text-muted">
          {timeoutError.detail}
        </p>
      ) : null}
    </div>
  );
}

/** Documents de la mission (panneau latéral) : tous ceux que l'utilisateur peut voir ou générer. */
export function MissionDocuments({ missionId }: { missionId: string }) {
  const available = useAvailableDocuments(missionId);
  if (available.isError) {
    return <p className="text-sm text-text-muted">{fr.documents.loadError}</p>;
  }
  if (!available.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  if (available.data.length === 0) {
    return <p className="text-sm text-text-muted">{fr.documents.noDocument}</p>;
  }
  return (
    <ul className="grid gap-3">
      {available.data.map((d) => (
        <li
          key={`${d.type_document}-${d.objet_id}`}
          className="border-b border-border pb-3 last:border-0 last:pb-0"
        >
          <DocumentRow disponible={d} timeoutError={available.timeoutError} />
        </li>
      ))}
    </ul>
  );
}
