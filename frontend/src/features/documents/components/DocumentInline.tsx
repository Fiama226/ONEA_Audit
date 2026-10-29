import { fr } from "@/i18n/fr";
import { useAvailableDocuments } from "../api";
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
  const disponible = available.data?.find(
    (d) => d.type_document === typeDocument && d.objet_id === objetId,
  );
  if (!disponible) return null;
  const version = disponible.document?.derniere_version ?? null;

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
      <GenerateDocumentButton disponible={disponible} />
      {version ? <DownloadButtons version={version} /> : null}
    </div>
  );
}
