import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { useRole } from "@/auth/useRole";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { RiskMatrix, type RiskMatrixCell } from "@/components/RiskMatrix";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { useProcesses, useRiskMap, useRiskMaps, useRiskMatrix, useRisks } from "../api";
import { ExportButtons } from "../components/ExportButtons";
import { FrozenBanner } from "../components/FrozenBanner";
import { NativeSelect } from "../components/NativeSelect";
import { RiskFilters } from "../components/RiskFilters";
import { RiskLevelBadge } from "../components/RiskLevelBadge";
import { VersionStatusBadge } from "../components/VersionStatusBadge";
import { ValidateRiskMapDialog } from "../components/ValidateRiskMapDialog";
import { PRIORITE_LABELS, REPONSE_LABELS } from "../labels";
import { canEditCartographie } from "../permissions";
import type { NiveauRisque, Risque } from "../types";

const PAGE_SIZE = 25;
const c = fr.refCartographie;

const columns: DataTableColumn<Risque>[] = [
  {
    id: "code",
    header: fr.referentiel.code,
    cell: ({ row }) => (
      <Link
        to={`/referentiel/risques/${row.original.id}`}
        className="font-medium text-primary underline-offset-4 hover:underline"
      >
        {row.original.code}
      </Link>
    ),
  },
  { id: "libelle", header: c.colRisque, accessorKey: "libelle" },
  { id: "processus", header: c.colProcessus, accessorKey: "processus_code" },
  { id: "probabilite", header: c.colP, accessorKey: "probabilite" },
  { id: "impact", header: c.colI, accessorKey: "impact" },
  { id: "score", header: c.colScore, accessorKey: "score" },
  {
    id: "niveau",
    header: c.colNiveau,
    cell: ({ row }) => <RiskLevelBadge niveau={row.original.niveau} />,
  },
  {
    id: "reponse",
    header: c.colReponse,
    cell: ({ row }) => (row.original.reponse ? REPONSE_LABELS[row.original.reponse] : c.noValue),
  },
  {
    id: "priorite",
    header: c.colPriorite,
    cell: ({ row }) => (row.original.priorite ? PRIORITE_LABELS[row.original.priorite] : c.noValue),
  },
];

function scale(value: string | null): 1 | 2 | 3 | 4 | 5 | null {
  const n = Number(value);
  return n >= 1 && n <= 5 && Number.isInteger(n) ? (n as 1 | 2 | 3 | 4 | 5) : null;
}

const NIVEAUX = ["FAIBLE", "MOYEN", "ELEVE"] as const;

export function RiskMapDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { role } = useRole();
  const [params, setParams] = useSearchParams();
  const [validating, setValidating] = useState(false);

  const probabilite = scale(params.get("probabilite"));
  const impact = scale(params.get("impact"));
  const cellFilter = probabilite && impact ? { probability: probabilite, impact } : null;
  const processus = params.get("processus") ?? "";
  const niveau = params.get("niveau") ?? "";
  const q = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);

  const map = useRiskMap(id);
  const matrix = useRiskMatrix(id);
  const others = useRiskMaps({ page_size: 100, ordering: "-annee" });
  const processes = useProcesses({ page_size: 200 });
  const risks = useRisks({
    version: id,
    probabilite: cellFilter?.probability,
    impact: cellFilter?.impact,
    processus,
    niveau: (NIVEAUX as readonly string[]).includes(niveau) ? (niveau as NiveauRisque) : undefined,
    q,
    page,
    page_size: PAGE_SIZE,
  });

  function update(changes: Record<string, string | null>, resetPage = true) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, value);
          else next.delete(key);
        }
        if (resetPage) next.delete("page");
        return next;
      },
      { replace: true },
    );
  }

  if (map.isLoading) {
    return (
      <div aria-busy="true" aria-label={fr.common.loading} className="grid gap-4">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (map.isError || !map.data || !id) {
    const notFound = isApiError(map.error) && map.error.status === 404;
    return (
      <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        <p>{notFound ? c.notFound : fr.errors.generic}</p>
        <Link to="/referentiel/cartographies" className="mt-3 inline-block text-primary underline">
          {c.backToList}
        </Link>
      </div>
    );
  }

  const version = map.data;
  const frozen = version.statut === "VALIDEE";
  const canEdit = canEditCartographie(role) && !frozen;
  const cells: RiskMatrixCell[] = (matrix.data?.cellules ?? []).map((cell) => ({
    probability: cell.probabilite as RiskMatrixCell["probability"],
    impact: cell.impact as RiskMatrixCell["impact"],
    count: cell.nombre,
    codes: cell.codes,
  }));
  const otherVersions = (others.data?.results ?? []).filter((v) => v.id !== id);
  const rows = risks.data?.results ?? [];
  const filtered = Boolean(cellFilter || processus || niveau || q);

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold">{`${c.detailTitle} ${version.annee}`}</h2>
          <VersionStatusBadge statut={version.statut} />
        </div>
        <div className="flex flex-wrap items-end gap-3 print:hidden">
          {canEdit && (
            <>
              <Button
                type="button"
                onClick={() => void navigate(`/referentiel/risques/nouveau?cartographie=${id}`)}
              >
                <Plus aria-hidden />
                {c.addRisk}
              </Button>
              <Button type="button" variant="outline" onClick={() => setValidating(true)}>
                {c.validate}
              </Button>
            </>
          )}
          <ExportButtons id={id} />
          {otherVersions.length > 0 && (
            <div className="grid gap-1">
              <Label htmlFor="compare-with" className="sr-only">
                {c.compareLabel}
              </Label>
              <NativeSelect
                id="compare-with"
                value=""
                onChange={(e) => {
                  if (e.target.value)
                    void navigate(
                      `/referentiel/cartographies/${id}/comparer?avec=${e.target.value}`,
                    );
                }}
              >
                <option value="">{c.compareWith}</option>
                {otherVersions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.libelle}
                  </option>
                ))}
              </NativeSelect>
            </div>
          )}
        </div>
      </div>

      {frozen && <FrozenBanner version={version} />}

      <section aria-labelledby="matrix-title" className="grid gap-3">
        <h3 id="matrix-title" className="text-base font-semibold">
          {c.matrixTitle}
        </h3>
        {matrix.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {c.matrixLoadError}
          </p>
        ) : (
          <>
            <RiskMatrix
              size="large"
              cells={matrix.isLoading ? [] : cells}
              selected={cellFilter}
              onSelect={(cell) =>
                cellFilter?.probability === cell.probability && cellFilter.impact === cell.impact
                  ? update({ probabilite: null, impact: null })
                  : update({
                      probabilite: String(cell.probability),
                      impact: String(cell.impact),
                    })
              }
            />
            {matrix.data && (
              <p className="text-sm text-text-muted">
                {matrix.data.total} {c.matrixSummary}
              </p>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="risks-title" className="grid gap-3">
        <h3 id="risks-title" className="text-base font-semibold">
          {c.risksTitle}
        </h3>
        <RiskFilters
          values={{ processus, niveau, q }}
          processes={processes.data?.results ?? []}
          onChange={(next) => update(next)}
        />
        {cellFilter && (
          <p className="flex items-center gap-3 text-sm" role="status">
            <span>
              {c.filterActive
                .replace("{p}", String(cellFilter.probability))
                .replace("{i}", String(cellFilter.impact))}
            </span>
            <span aria-hidden>·</span>
            <Button
              type="button"
              variant="link"
              className="h-auto p-0 print:hidden"
              onClick={() => update({ probabilite: null, impact: null })}
            >
              {c.clearFilter}
            </Button>
          </p>
        )}
        {risks.isError ? (
          <div role="alert" className="rounded-lg border border-border bg-surface p-4 text-sm">
            <p>{c.risksLoadError}</p>
            <Button
              type="button"
              variant="outline"
              className="mt-3"
              onClick={() => void risks.refetch()}
            >
              {fr.common.retry}
            </Button>
          </div>
        ) : (
          <DataTable
            caption={c.risksCaption}
            columns={columns}
            data={rows}
            total={risks.data?.count ?? 0}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={(next) => update({ page: String(next) }, false)}
            isLoading={risks.isLoading}
            empty={
              <p className="rounded-lg border border-border bg-surface p-6 text-sm text-text-muted">
                {filtered ? c.risksEmpty : c.risksEmptyMap}
              </p>
            }
          />
        )}
      </section>

      {canEdit && <ValidateRiskMapDialog id={id} open={validating} onOpenChange={setValidating} />}
    </div>
  );
}
