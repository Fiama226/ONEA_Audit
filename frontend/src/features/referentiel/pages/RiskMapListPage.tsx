import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useRole } from "@/auth/useRole";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useRiskMaps } from "../api";
import { CreateRiskMapDialog } from "../components/CreateRiskMapDialog";
import { VersionStatusBadge } from "../components/VersionStatusBadge";
import { canEditCartographie } from "../permissions";
import type { CartographieVersion } from "../types";

const PAGE_SIZE = 25;
const c = fr.refCartographie;

const columns: DataTableColumn<CartographieVersion>[] = [
  {
    id: "annee",
    header: c.colAnnee,
    enableSorting: false,
    cell: ({ row }) => (
      <Link
        to={`/referentiel/cartographies/${row.original.id}`}
        className="font-medium text-primary underline-offset-4 hover:underline"
      >
        {row.original.annee}
      </Link>
    ),
  },
  { id: "libelle", header: c.colLibelle, enableSorting: false, accessorKey: "libelle" },
  {
    id: "statut",
    header: c.colStatut,
    enableSorting: false,
    cell: ({ row }) => <VersionStatusBadge statut={row.original.statut} />,
  },
  { id: "nb_risques", header: c.colNbRisques, enableSorting: false, accessorKey: "nb_risques" },
  {
    id: "validee_le",
    header: c.colValideeLe,
    enableSorting: false,
    cell: ({ row }) => (row.original.validee_le ? formatDate(row.original.validee_le) : c.noValue),
  },
  {
    id: "validee_par",
    header: c.colValideePar,
    enableSorting: false,
    cell: ({ row }) => row.original.validee_par?.nom_complet ?? c.noValue,
  },
];

export function RiskMapListPage() {
  const { role } = useRole();
  const canEdit = canEditCartographie(role);
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [creating, setCreating] = useState(false);
  const query = useRiskMaps({ page, page_size: PAGE_SIZE, ordering: "-annee" });
  const versions = query.data?.results ?? [];

  const createButton = canEdit ? (
    <Button type="button" onClick={() => setCreating(true)}>
      <Plus aria-hidden />
      {c.createAction}
    </Button>
  ) : null;

  let body;
  if (query.isError) {
    body = (
      <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        <p>{c.loadError}</p>
        <Button
          type="button"
          variant="outline"
          className="mt-3"
          onClick={() => void query.refetch()}
        >
          {fr.common.retry}
        </Button>
      </div>
    );
  } else {
    body = (
      <DataTable
        caption={c.listCaption}
        columns={columns}
        data={versions}
        total={query.data?.count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={(next) =>
          setParams((p) => {
            p.set("page", String(next));
            return p;
          })
        }
        isLoading={query.isLoading}
        empty={
          <EmptyState
            title={c.emptyTitle}
            description={canEdit ? c.emptyRai : c.emptyOther}
            illustration={false}
          >
            {createButton}
          </EmptyState>
        }
      />
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{fr.referentiel.pageCartographies}</h2>
        {versions.length > 0 && createButton}
      </div>
      {body}
      {canEdit && <CreateRiskMapDialog open={creating} onOpenChange={setCreating} />}
    </div>
  );
}
