import { AlertTriangle } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { ALERT_CLASS } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useReminders } from "../api";
import { StatusChips, type Chip } from "../components/StatusChips";
import type { Relance, StatutRelance } from "../types";

const t = fr.suiviJournaux;
const PAGE_SIZE = 25;
const STATUTS: readonly StatutRelance[] = ["A_ENVOYER", "ENVOYEE", "ECHEC", "SANS_ADRESSE"];

const CHIPS: readonly Chip[] = [
  { value: "", label: t.chipAll },
  { value: "ECHEC", label: t.chipFailed },
  { value: "SANS_ADRESSE", label: t.chipNoAddress },
  { value: "A_ENVOYER", label: t.chipToSend },
  { value: "ENVOYEE", label: t.chipSent },
];

const STATUS_LABELS: Record<StatutRelance, string> = {
  A_ENVOYER: t.statusA_ENVOYER,
  ENVOYEE: t.statusENVOYEE,
  ECHEC: t.statusECHEC,
  SANS_ADRESSE: t.statusSANS_ADRESSE,
};

const STAGE_LABELS: Record<Relance["palier"], string> = {
  J_MOINS_15: t.stageJ_MOINS_15,
  J: t.stageJ,
  J_PLUS_15: t.stageJ_PLUS_15,
};

const COLUMNS: DataTableColumn<Relance>[] = [
  {
    id: "mission",
    header: t.colMission,
    enableSorting: false,
    cell: ({ row }) => row.original.mission_reference,
  },
  {
    id: "action",
    header: t.colAction,
    enableSorting: false,
    cell: ({ row }) => (
      <Link
        to={`/recommandations/actions/${row.original.suivi}`}
        className="font-medium text-primary underline-offset-2 hover:underline"
      >
        {row.original.action_libelle}
      </Link>
    ),
  },
  {
    id: "palier",
    header: t.colStage,
    enableSorting: false,
    cell: ({ row }) => STAGE_LABELS[row.original.palier],
  },
  {
    id: "echeance_reference",
    header: t.colRefDue,
    enableSorting: false,
    cell: ({ row }) => (
      <time dateTime={row.original.echeance_reference}>
        {formatDate(row.original.echeance_reference)}
      </time>
    ),
  },
  {
    id: "destinataire",
    header: t.colRecipient,
    enableSorting: false,
    cell: ({ row }) => row.original.destinataire.nom_complet,
  },
  {
    id: "statut",
    header: t.colStatus,
    enableSorting: false,
    cell: ({ row }) => {
      const { statut } = row.original;
      const problem = statut === "ECHEC" || statut === "SANS_ADRESSE";
      return (
        <span className="inline-flex items-center gap-1.5">
          {problem && <AlertTriangle aria-hidden className="size-3.5 text-destructive" />}
          {STATUS_LABELS[statut]}
        </span>
      );
    },
  },
  {
    id: "tentatives",
    header: t.colAttempts,
    enableSorting: false,
    cell: ({ row }) => row.original.tentatives,
  },
  {
    id: "erreur",
    header: t.colError,
    enableSorting: false,
    cell: ({ row }) =>
      row.original.statut === "SANS_ADRESSE" ? t.noAddressHint : row.original.erreur || "—",
  },
];

/**
 * Journal des relances (RAI). Cibles des liens « Relances en échec » (`?statut=ECHEC`) et
 * « Relances sans adresse » (`?statut=SANS_ADRESSE`) de la file de décisions.
 */
export function RemindersPage() {
  const [search, setSearch] = useSearchParams();
  const raw = search.get("statut") ?? "";
  const statut = STATUTS.find((s) => s === raw);
  const page = Math.max(1, Number(search.get("page")) || 1);
  const query = useReminders({ statut });

  function change(value: string) {
    setSearch(value ? { statut: value } : {}, { replace: true });
  }

  const rows = query.data?.results ?? [];
  const loadFailed = query.isError && query.data === undefined;

  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold tracking-[-0.012em]">{t.remindersTitle}</h1>
      <p className="mb-6 text-sm">
        <Link to="/" className="text-primary underline-offset-2 hover:underline">
          {t.backToQueue}
        </Link>
      </p>
      <div className="mb-4">
        <StatusChips label={t.filtersLabel} chips={CHIPS} value={statut ?? ""} onChange={change} />
      </div>
      {loadFailed ? (
        <p role="alert" className={ALERT_CLASS}>
          {t.loadError}
        </p>
      ) : (
        <DataTable
          caption={t.captionReminders}
          columns={COLUMNS}
          data={rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)}
          total={query.data?.count ?? 0}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) =>
            setSearch(
              (previous) => {
                const next = new URLSearchParams(previous);
                if (p > 1) next.set("page", String(p));
                else next.delete("page");
                return next;
              },
              { replace: true },
            )
          }
          isLoading={query.isLoading}
          empty={<p className="rounded-lg border border-border p-6 text-sm">{t.remindersEmpty}</p>}
          paginationLabel={t.captionReminders}
        />
      )}
    </div>
  );
}
