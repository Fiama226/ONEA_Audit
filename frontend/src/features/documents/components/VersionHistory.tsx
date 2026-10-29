import { ApiError } from "@/api/errors";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useConsultations } from "../api";
import { gabaritLabel } from "../labels";
import type { Document, DocumentVersion } from "../types";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { HashDisplay } from "./HashDisplay";

function DownloadCount({ versionId }: { versionId: string }) {
  const consultations = useConsultations(versionId);
  if (consultations.data) return <>{consultations.data.count}</>;
  return (
    <span className="text-text-muted">{consultations.error instanceof ApiError ? "—" : "…"}</span>
  );
}

const COLUMNS: DataTableColumn<DocumentVersion>[] = [
  {
    id: "numero_version",
    header: fr.documents.colVersion,
    cell: ({ row }) => `v${row.original.numero_version}`,
    enableSorting: false,
  },
  {
    id: "genere_le",
    header: fr.documents.colGeneratedAt,
    cell: ({ row }) =>
      row.original.genere_le ? formatDateTime(row.original.genere_le) : fr.documents.notGenerated,
    enableSorting: false,
  },
  {
    id: "par",
    header: fr.documents.colBy,
    cell: ({ row }) => row.original.demandee_par.nom_complet || row.original.demandee_par.username,
    enableSorting: false,
  },
  {
    id: "gabarit",
    header: fr.documents.colTemplate,
    cell: ({ row }) => gabaritLabel(row.original.gabarit),
    enableSorting: false,
  },
  {
    id: "empreinte",
    header: fr.documents.colHash,
    cell: ({ row }) => <HashDisplay value={row.original.empreinte_docx} />,
    enableSorting: false,
  },
  {
    id: "statut",
    header: fr.documents.colStatus,
    cell: ({ row }) => <DocumentStatusBadge version={row.original} />,
    enableSorting: false,
  },
  {
    id: "telechargements",
    header: fr.documents.colDownloads,
    cell: ({ row }) => <DownloadCount versionId={row.original.id} />,
    enableSorting: false,
  },
];

/** Historique des versions d'un document (la plus récente d'abord, ordre fourni par le serveur). */
export function VersionHistory({ document }: { document: Document }) {
  const versions = document.versions;
  return (
    <DataTable
      caption={fr.documents.historyCaption}
      columns={COLUMNS}
      data={versions}
      total={versions.length}
      page={1}
      pageSize={Math.max(versions.length, 1)}
      onPageChange={() => undefined}
      isLoading={false}
      empty={<p className="text-sm text-text-muted">{fr.documents.noVersions}</p>}
    />
  );
}
