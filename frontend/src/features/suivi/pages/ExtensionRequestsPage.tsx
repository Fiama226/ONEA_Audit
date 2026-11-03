import { Link, useSearchParams } from "react-router-dom";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { ALERT_CLASS } from "@/components/form/FormField";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useExtensionJournal } from "../api";
import { StatusChips, type Chip } from "../components/StatusChips";
import { STATUT_REPORT_LABELS } from "../labels";
import type { DemandeReportListe, StatutDemandeReport } from "../types";

const t = fr.suiviJournaux;
const PAGE_SIZE = 25;
const STATUTS: readonly StatutDemandeReport[] = ["EN_ATTENTE", "ACCEPTEE", "REFUSEE"];

const CHIPS: readonly Chip[] = [
  { value: "", label: t.chipAll },
  { value: "EN_ATTENTE", label: t.chipPending },
  { value: "ACCEPTEE", label: t.chipAccepted },
  { value: "REFUSEE", label: t.chipRefused },
];

const COLUMNS: DataTableColumn<DemandeReportListe>[] = [
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
        to={`/recommandations/actions/${row.original.action}`}
        className="font-medium text-primary underline-offset-2 hover:underline"
      >
        {row.original.action_libelle}
      </Link>
    ),
  },
  {
    id: "echeance_actuelle",
    header: t.colCurrentDue,
    enableSorting: false,
    cell: ({ row }) => (
      <time dateTime={row.original.echeance_actuelle}>
        {formatDate(row.original.echeance_actuelle)}
      </time>
    ),
  },
  {
    id: "nouvelle_echeance",
    header: t.colNewDue,
    enableSorting: false,
    cell: ({ row }) => (
      <time dateTime={row.original.nouvelle_echeance}>
        {formatDate(row.original.nouvelle_echeance)}
      </time>
    ),
  },
  {
    id: "demandeur",
    header: t.colRequester,
    enableSorting: false,
    cell: ({ row }) => row.original.demandee_par.nom_complet,
  },
  {
    id: "statut",
    header: t.colStatus,
    enableSorting: false,
    cell: ({ row }) => STATUT_REPORT_LABELS[row.original.statut],
  },
];

/**
 * Demandes de report d'échéance (RAI). Cible du lien « Reports en attente » de la file de
 * décisions : `?statut=EN_ATTENTE`. Le filtre est lu dans l'URL (lien partageable).
 */
export function ExtensionRequestsPage() {
  const [search, setSearch] = useSearchParams();
  const raw = search.get("statut") ?? "";
  const statut = STATUTS.find((s) => s === raw);
  const page = Math.max(1, Number(search.get("page")) || 1);
  const query = useExtensionJournal({ statut });

  function change(value: string) {
    setSearch(value ? { statut: value } : {}, { replace: true });
  }

  const rows = query.data?.results ?? [];
  const loadFailed = query.isError && query.data === undefined;

  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold tracking-[-0.012em]">{t.extensionsTitle}</h1>
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
          caption={t.captionExtensions}
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
          empty={<p className="rounded-lg border border-border p-6 text-sm">{t.extensionsEmpty}</p>}
          paginationLabel={t.captionExtensions}
        />
      )}
    </div>
  );
}
