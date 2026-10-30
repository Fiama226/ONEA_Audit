import { Link } from "react-router-dom";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { fr } from "@/i18n/fr";
import type { ActionSuivie } from "../types";
import { DueDateCell } from "./DueDateCell";
import { SuiviStatusBadge } from "./SuiviStatusBadge";

const t = fr.suiviRegistre;

type Props = {
  actions: ActionSuivie[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  ordering?: string;
  onOrderingChange: (ordering: string) => void;
  isLoading: boolean;
};

const COLUMNS: DataTableColumn<ActionSuivie>[] = [
  {
    id: "action",
    header: t.colAction,
    enableSorting: false,
    cell: ({ row }) => (
      <Link
        to={`/recommandations/actions/${row.original.id}`}
        className="font-medium text-primary underline-offset-2 hover:underline"
      >
        {row.original.action_libelle}
      </Link>
    ),
  },
  {
    id: "mission",
    header: t.colMission,
    enableSorting: false,
    cell: ({ row }) => row.original.mission.reference,
  },
  {
    id: "recommandation",
    header: t.colRecommendation,
    enableSorting: false,
    cell: ({ row }) => row.original.recommandation.libelle,
  },
  {
    id: "responsable",
    header: t.colResponsible,
    enableSorting: false,
    cell: ({ row }) => row.original.responsable.nom_complet,
  },
  {
    id: "echeance",
    header: t.colDue,
    cell: ({ row }) => (
      <DueDateCell
        echeance={row.original.echeance}
        enRetard={row.original.en_retard}
        joursRetard={row.original.jours_retard}
      />
    ),
  },
  {
    id: "statut",
    header: t.colStatus,
    cell: ({ row }) => <SuiviStatusBadge statut={row.original.statut} />,
  },
];

/** Registre des actions. La page traite le chargement en erreur avant de rendre ce tableau. */
export function ActionsTable(props: Props) {
  return (
    <DataTable
      caption={t.captionActions}
      columns={COLUMNS}
      data={props.actions}
      total={props.total}
      page={props.page}
      pageSize={props.pageSize}
      onPageChange={props.onPageChange}
      ordering={props.ordering}
      onOrderingChange={props.onOrderingChange}
      isLoading={props.isLoading}
      empty={<p className="rounded-lg border border-border p-6 text-sm">{t.emptyActions}</p>}
      paginationLabel={t.captionActions}
    />
  );
}
