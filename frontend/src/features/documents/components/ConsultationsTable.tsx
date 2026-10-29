import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { ALERT_CLASS } from "@/components/form/FormField";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useConsultations } from "../api";
import type { Consultation } from "../types";

const t = fr.documentsRegistre;

const COLUMNS: DataTableColumn<Consultation>[] = [
  {
    id: "utilisateur",
    header: t.colUser,
    enableSorting: false,
    cell: ({ row }) => row.original.utilisateur.nom_complet || row.original.utilisateur.username,
  },
  {
    id: "le",
    header: t.colDateTime,
    enableSorting: false,
    cell: ({ row }) => formatDateTime(row.original.le),
  },
  {
    id: "format",
    header: t.colFormat,
    enableSorting: false,
    cell: ({ row }) => (row.original.format === "PDF" ? t.formatPdf : t.formatDocx),
  },
  {
    id: "adresse_ip",
    header: t.colIp,
    enableSorting: false,
    cell: ({ row }) => row.original.adresse_ip ?? "—",
  },
];

/** Consultations (téléchargements) d'une version ; réservé au RAI, l'appelant masque le composant sinon. */
export function ConsultationsTable({ versionId }: { versionId: string }) {
  const { data, isLoading, isError } = useConsultations(versionId);
  if (isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.consultationsError}
      </p>
    );
  }
  const rows = data?.results ?? [];
  return (
    <div className="grid gap-2">
      <DataTable
        caption={t.consultationsCaption}
        columns={COLUMNS}
        data={rows}
        total={data?.count ?? 0}
        page={1}
        pageSize={Math.max(rows.length, 1)}
        onPageChange={() => undefined}
        isLoading={isLoading}
        paginationLabel={`${fr.table.pagination} — ${t.consultationsCaption}`}
        empty={<p className="text-sm text-text-muted">{t.consultationsEmpty}</p>}
      />
      {data ? <ListIncompleteAlert count={data.count} loaded={rows.length} /> : null}
    </div>
  );
}
