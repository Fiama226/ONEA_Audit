import { Pencil, Plus, Printer, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { useRole } from "@/auth/useRole";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { RiskMatrix, type RiskMatrixCell } from "@/components/RiskMatrix";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import {
  fetchAllRisks,
  useDeleteRiskMap,
  useProcesses,
  useRiskMap,
  useRiskMaps,
  useRiskMatrix,
  useRisks,
} from "../api";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { EditRiskMapDialog } from "../components/EditRiskMapDialog";
import { ExportButtons } from "../components/ExportButtons";
import { FrozenBanner } from "../components/FrozenBanner";
import { NativeSelect } from "@/components/form/NativeSelect";
import { RiskFilters } from "../components/RiskFilters";
import { RiskLevelBadge } from "../components/RiskLevelBadge";
import { VersionStatusBadge } from "../components/VersionStatusBadge";
import { ValidateRiskMapDialog } from "../components/ValidateRiskMapDialog";
import { NIVEAU_LABELS, PRIORITE_LABELS, REPONSE_LABELS } from "../labels";
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

/** Tableau complet réservé à l'impression (tous les risques du jeu filtré, sans actions). */
function PrintTable({ rows }: { rows: Risque[] }) {
  const heads = [
    fr.referentiel.code,
    c.colRisque,
    c.colProcessus,
    c.colP,
    c.colI,
    c.colScore,
    c.colNiveau,
    c.colReponse,
    c.colPriorite,
  ];
  return (
    <table className="hidden w-full text-xs print:table">
      <caption className="sr-only">{c.risksCaption}</caption>
      <thead>
        <tr>
          {heads.map((h) => (
            <th key={h} scope="col" className="border-b border-border px-2 py-1 text-left">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="break-inside-avoid">
            <td className="px-2 py-1">{r.code}</td>
            <td className="px-2 py-1">{r.libelle}</td>
            <td className="px-2 py-1">{r.processus_code}</td>
            <td className="px-2 py-1">{r.probabilite}</td>
            <td className="px-2 py-1">{r.impact}</td>
            <td className="px-2 py-1">{r.score}</td>
            <td className="px-2 py-1">{NIVEAU_LABELS[r.niveau]}</td>
            <td className="px-2 py-1">{r.reponse ? REPONSE_LABELS[r.reponse] : c.noValue}</td>
            <td className="px-2 py-1">{r.priorite ? PRIORITE_LABELS[r.priorite] : c.noValue}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function RiskMapDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { role } = useRole();
  const [params, setParams] = useSearchParams();
  const [validating, setValidating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const deleteMap = useDeleteRiskMap();
  const [compareChoice, setCompareChoice] = useState("");
  const [printRows, setPrintRows] = useState<Risque[] | null>(null);
  const [printing, setPrinting] = useState(false);
  const [printError, setPrintError] = useState(false);

  const probabilite = scale(params.get("probabilite"));
  const impact = scale(params.get("impact"));
  const cellFilter = probabilite && impact ? { probability: probabilite, impact } : null;
  const processus = params.get("processus") ?? "";
  const niveau = params.get("niveau") ?? "";
  const q = params.get("q") ?? "";
  // La saisie est locale ; l'URL (donc la requête) n'est mise à jour qu'après 300 ms d'inactivité.
  const [qInput, setQInput] = useState(q);
  const pushedQ = useRef(q);
  // Retour/avance du navigateur : si `q` change sans que ce soit notre propre mise à jour,
  // la saisie locale suit l'URL.
  useEffect(() => {
    if (q !== pushedQ.current) {
      pushedQ.current = q;
      setQInput(q);
    }
  }, [q]);
  useEffect(() => {
    if (qInput === q) return;
    const timer = setTimeout(() => {
      pushedQ.current = qInput;
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (qInput) next.set("q", qInput);
          else next.delete("q");
          next.delete("page");
          return next;
        },
        { replace: true },
      );
    }, 300);
    return () => clearTimeout(timer);
  }, [qInput, q, setParams]);
  const page = Math.max(1, Number(params.get("page")) || 1);

  const map = useRiskMap(id);
  const matrix = useRiskMatrix(id);
  const others = useRiskMaps({ page_size: 100, ordering: "-annee" });
  const processes = useProcesses({ page_size: 200 });
  const filterParams = {
    version: id,
    probabilite: cellFilter?.probability,
    impact: cellFilter?.impact,
    processus,
    niveau: (NIVEAUX as readonly string[]).includes(niveau) ? (niveau as NiveauRisque) : undefined,
    q,
  };
  const risks = useRisks({ ...filterParams, page, page_size: PAGE_SIZE });

  // Impression complète : charge toutes les pages du jeu filtré, puis imprime.
  async function startPrint() {
    setPrinting(true);
    setPrintError(false);
    try {
      const all = await fetchAllRisks(filterParams);
      // Rendu synchrone du tableau complet (réservé à l'impression) avant d'ouvrir le dialogue.
      flushSync(() => setPrintRows(all));
      window.print();
      setPrintRows(null);
    } catch {
      setPrintError(true);
    } finally {
      setPrinting(false);
    }
  }

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
  const pageCount = Math.ceil((risks.data?.count ?? 0) / PAGE_SIZE);

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
                onClick={() => void navigate(`/referentiel/cartographies/${id}/risques/nouveau`)}
              >
                <Plus aria-hidden />
                {c.addRisk}
              </Button>
              <Button type="button" variant="outline" onClick={() => setValidating(true)}>
                {c.validate}
              </Button>
              <Button type="button" variant="outline" onClick={() => setEditing(true)}>
                <Pencil aria-hidden />
                {c.editDraft}
              </Button>
              <Button type="button" variant="outline" onClick={() => setDeleting(true)}>
                <Trash2 aria-hidden />
                {c.deleteDraft}
              </Button>
            </>
          )}
          <ExportButtons id={id} />
          <Button
            type="button"
            variant="outline"
            disabled={printing}
            onClick={() => void startPrint()}
          >
            <Printer aria-hidden />
            {printing ? c.printPreparing : c.printAction}
          </Button>
          {otherVersions.length > 0 && (
            <form
              className="flex items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (compareChoice)
                  void navigate(`/referentiel/cartographies/${id}/comparer?avec=${compareChoice}`);
              }}
            >
              <div className="grid gap-1">
                <Label htmlFor="compare-with" className="sr-only">
                  {c.compareLabel}
                </Label>
                <NativeSelect
                  id="compare-with"
                  value={compareChoice}
                  onChange={(e) => setCompareChoice(e.target.value)}
                >
                  <option value="">{c.compareWith}</option>
                  {otherVersions.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.libelle}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <Button type="submit" variant="outline" disabled={!compareChoice}>
                {c.compareButton}
              </Button>
            </form>
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
          values={{ processus, niveau, q: qInput }}
          processes={processes.data?.results ?? []}
          onChange={({ q: nextQ, ...rest }) => {
            if (nextQ !== undefined) setQInput(nextQ);
            if (Object.keys(rest).length > 0) update(rest);
          }}
        />
        {printError && (
          <p role="alert" className="text-sm text-destructive print:hidden">
            {c.printError}
          </p>
        )}
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
          <>
            <div className={printRows ? "print:hidden" : undefined}>
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
            </div>
            {pageCount > 1 && !printRows && (
              <p className="hidden text-sm print:block">
                {c.printPartial.replace("{p}", String(page)).replace("{n}", String(pageCount))}
              </p>
            )}
            {printRows && <PrintTable rows={printRows} />}
          </>
        )}
      </section>

      {canEdit && <ValidateRiskMapDialog id={id} open={validating} onOpenChange={setValidating} />}
      {canEdit && <EditRiskMapDialog version={version} open={editing} onOpenChange={setEditing} />}
      {canEdit && (
        <ConfirmDeleteDialog
          open={deleting}
          onOpenChange={setDeleting}
          title={c.deleteDraftTitle}
          description={c.deleteDraftWarning}
          onConfirm={async () => {
            await deleteMap.mutateAsync(id);
            void navigate("/referentiel/cartographies");
          }}
          restoreFocus={() => undefined}
        />
      )}
    </div>
  );
}
