import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useRole } from "@/auth/useRole";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useAuditPlans } from "../api";
import { CreatePlanDialog } from "../components/CreatePlanDialog";
import { PlanStatusBadge } from "../components/PlanStatusBadge";
import { formatDays } from "../format";
import { canEditAuditPlan } from "../permissions";
import type { AuditPlan } from "../types";

const PAGE_SIZE = 25;
const p = fr.programmation;
const c = fr.programmationPlans;

const columns: DataTableColumn<AuditPlan>[] = [
  {
    id: "annee",
    header: p.year,
    enableSorting: false,
    cell: ({ row }) => (
      <Link
        to={`/programme-annuel/${row.original.id}`}
        className="font-medium text-primary underline-offset-4 hover:underline"
      >
        {row.original.annee}
      </Link>
    ),
  },
  { id: "libelle", header: p.label, enableSorting: false, accessorKey: "libelle" },
  {
    id: "statut",
    header: p.status,
    enableSorting: false,
    cell: ({ row }) => <PlanStatusBadge statut={row.original.statut} />,
  },
  {
    id: "nb_lignes",
    header: p.lineCount,
    enableSorting: false,
    cell: ({ row }) => <span className="tabular-nums">{row.original.nb_lignes}</span>,
  },
  {
    id: "charge",
    header: c.totalLoadColumn,
    enableSorting: false,
    cell: ({ row }) => (
      <span className="tabular-nums">{formatDays(row.original.charge_totale_jours)}</span>
    ),
  },
  {
    id: "valide_le",
    header: p.validatedOn,
    enableSorting: false,
    cell: ({ row }) => (row.original.valide_le ? formatDate(row.original.valide_le) : c.noValue),
  },
  {
    id: "valide_par",
    header: p.validatedBy,
    enableSorting: false,
    cell: ({ row }) => row.original.valide_par?.nom_complet ?? c.noValue,
  },
];

export function AuditPlanListPage() {
  const { role } = useRole();
  const canEdit = canEditAuditPlan(role);
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [creating, setCreating] = useState(false);
  const query = useAuditPlans({ page, page_size: PAGE_SIZE, ordering: "-annee" });
  const plans = query.data?.results ?? [];

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
        data={plans}
        total={query.data?.count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={(next) =>
          setParams((prev) => {
            const nextParams = new URLSearchParams(prev);
            nextParams.set("page", String(next));
            return nextParams;
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
        <h1 className="text-2xl font-semibold">{p.title}</h1>
        {plans.length > 0 && createButton}
      </div>
      {body}
      {canEdit && (
        <CreatePlanDialog
          open={creating}
          onOpenChange={setCreating}
          existingYears={plans.map((plan) => plan.annee)}
        />
      )}
    </div>
  );
}
