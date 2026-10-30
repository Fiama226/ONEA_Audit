import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { ALERT_CLASS } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { Label } from "@/components/ui/label";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useDistributedReports } from "../api";
import { AppreciationBadge } from "../components/AppreciationBadge";
import type { RapportDiffuse } from "../types";

const t = fr.rapportFinal;
const PAGE_SIZE = 20;

const year = (iso: string | null) => (iso ? new Date(iso).getUTCFullYear() : null);
const dateOrDash = (iso: string | null) => (iso ? formatDate(iso) : "—");

const COLUMNS: DataTableColumn<RapportDiffuse>[] = [
  {
    id: "mission",
    header: t.colMission,
    enableSorting: false,
    cell: ({ row }) => (
      <Link className="font-medium underline" to={`/rapports/${row.original.id}`}>
        {row.original.mission_reference} · {row.original.mission_titre}
      </Link>
    ),
  },
  {
    id: "numero_document",
    header: t.colNumber,
    enableSorting: false,
    cell: ({ row }) => row.original.numero_document || "—",
  },
  {
    id: "valide_le",
    header: t.colValidated,
    enableSorting: false,
    cell: ({ row }) => dateOrDash(row.original.valide_le),
  },
  {
    id: "diffuse_le",
    header: t.colDistributed,
    enableSorting: false,
    cell: ({ row }) => dateOrDash(row.original.diffuse_le),
  },
  {
    id: "appreciation",
    header: t.colAppreciation,
    enableSorting: false,
    cell: ({ row }) => <AppreciationBadge appreciation={row.original.appreciation_globale} />,
  },
  {
    id: "accuse",
    header: t.colAck,
    enableSorting: false,
    cell: ({ row }) =>
      row.original.mon_accuse_reception
        ? t.ackDone.replace("{date}", formatDate(row.original.mon_accuse_reception))
        : t.ackNone,
  },
];

/** Rapports diffusés visibles de l'utilisateur ; aucune information interne de la mission. */
export function RapportsDiffusesPage() {
  const { me } = useAuth();
  const reports = useDistributedReports();
  const [selectedYear, setSelectedYear] = useState("");
  const [page, setPage] = useState(1);

  const rows = reports.data?.results;
  const years = useMemo(
    () =>
      [...new Set((rows ?? []).map((r) => year(r.diffuse_le)).filter((y) => y !== null))].sort(
        (a, b) => b - a,
      ),
    [rows],
  );
  const filtered = (rows ?? []).filter(
    (r) => selectedYear === "" || String(year(r.diffuse_le)) === selectedYear,
  );

  const empty =
    me?.role === "DG" ? t.distEmptyDg : me?.role === "RAI" ? t.distEmptyRai : t.distEmptyOther;

  let body;
  if (reports.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.distLoadError}
      </p>
    );
  } else {
    body = (
      <DataTable
        caption={fr.communication.distributedTitle}
        columns={COLUMNS}
        data={filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)}
        total={filtered.length}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        isLoading={reports.isPending}
        empty={<p className="text-sm text-text-muted">{empty}</p>}
      />
    );
  }

  return (
    <section aria-labelledby="rapports-diffuses-title" className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="rapports-diffuses-title" className="text-lg font-semibold">
          {fr.communication.distributedTitle}
        </h2>
        {years.length > 0 && (
          <div className="flex items-center gap-2">
            <Label htmlFor="distributed-year">{t.distYear}</Label>
            <NativeSelect
              id="distributed-year"
              className="w-40"
              value={selectedYear}
              onChange={(e) => {
                setSelectedYear(e.target.value);
                setPage(1);
              }}
            >
              <option value="">{t.distAllYears}</option>
              {years.map((y) => (
                <option key={y} value={String(y)}>
                  {y}
                </option>
              ))}
            </NativeSelect>
          </div>
        )}
      </div>
      {body}
    </section>
  );
}
