import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { fr } from "@/i18n/fr";
import { STATUT_RECOMMANDATION_SUIVI_LABELS } from "../labels";
import type { RecommandationSuivie } from "../types";
import { DueDateCell } from "./DueDateCell";
import { PriorityBadge } from "./PriorityBadge";

const t = fr.suiviRegistre;

type Props = {
  recommendations: RecommandationSuivie[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  ordering?: string;
  onOrderingChange: (ordering: string) => void;
  isLoading: boolean;
};

const COLUMNS: DataTableColumn<RecommandationSuivie>[] = [
  {
    id: "libelle",
    header: t.colRecommendation,
    enableSorting: false,
    cell: ({ row }) => <span className="font-medium">{row.original.libelle}</span>,
  },
  {
    id: "mission",
    header: t.colMission,
    enableSorting: false,
    cell: ({ row }) => row.original.mission.reference,
  },
  {
    id: "entite",
    header: t.colEntity,
    enableSorting: false,
    cell: ({ row }) => row.original.entite.code,
  },
  {
    id: "priorite",
    header: t.colPriority,
    cell: ({ row }) => <PriorityBadge priorite={row.original.priorite} />,
  },
  {
    id: "statut_suivi",
    header: t.colStatus,
    enableSorting: false,
    cell: ({ row }) => STATUT_RECOMMANDATION_SUIVI_LABELS[row.original.statut_suivi],
  },
  {
    id: "actions",
    header: t.colActionsCount,
    enableSorting: false,
    cell: ({ row }) => (
      <span>
        {t.actionsProgress
          .replace("{closed}", String(row.original.actions_closes))
          .replace("{total}", String(row.original.actions_total))}
        {row.original.actions_en_retard > 0 && (
          <span className="block text-xs font-medium text-destructive">
            {t.actionsOverdue.replace("{n}", String(row.original.actions_en_retard))}
          </span>
        )}
      </span>
    ),
  },
  {
    id: "prochaine_echeance",
    header: t.colNextDue,
    cell: ({ row }) => <DueDateCell echeance={row.original.prochaine_echeance} />,
  },
];

/** Registre des recommandations. La page traite le chargement en erreur avant ce tableau. */
export function RecommendationsTable(props: Props) {
  return (
    <DataTable
      caption={t.captionRecommendations}
      columns={COLUMNS}
      data={props.recommendations}
      total={props.total}
      page={props.page}
      pageSize={props.pageSize}
      onPageChange={props.onPageChange}
      ordering={props.ordering}
      onOrderingChange={props.onOrderingChange}
      isLoading={props.isLoading}
      empty={
        <p className="rounded-lg border border-border p-6 text-sm">{t.emptyRecommendations}</p>
      }
      paginationLabel={t.captionRecommendations}
    />
  );
}
