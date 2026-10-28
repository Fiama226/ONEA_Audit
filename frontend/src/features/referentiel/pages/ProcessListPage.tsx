import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { useAuth } from "@/auth/useAuth";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fr } from "@/i18n/fr";
import { useProcesses, type ProcessParams } from "../api";
import { ALERT_CLASS, SELECT_CLASS } from "../components/FormField";
import { FAMILLE_LABELS } from "../labels";
import { canEditStructure } from "../permissions";
import type { FamilleProcessus, Processus } from "../types";

const s = fr.refStructure;
const PAGE_SIZE = 20;
const FAMILIES = Object.keys(FAMILLE_LABELS) as FamilleProcessus[];

const COLUMNS: DataTableColumn<Processus>[] = [
  { id: "code", accessorKey: "code", header: fr.referentiel.code },
  {
    id: "libelle",
    accessorKey: "libelle",
    header: s.viewProcessTitle,
    cell: ({ row }) => (
      <Link
        to={row.original.id}
        className="font-medium text-primary underline-offset-[3px] hover:underline focus-visible:outline-2 focus-visible:outline-ring"
      >
        {row.original.libelle}
      </Link>
    ),
  },
  {
    id: "famille",
    accessorKey: "famille",
    header: fr.referentiel.famille,
    cell: ({ row }) => FAMILLE_LABELS[row.original.famille],
  },
  {
    id: "directions",
    header: fr.referentiel.directionsRattachees,
    enableSorting: false,
    cell: ({ row }) => row.original.directions_detail.map((d) => d.code).join(", ") || "-",
  },
  { id: "ordre", accessorKey: "ordre", header: fr.referentiel.ordre },
];

export function ProcessListPage() {
  const { me } = useAuth();
  const editable = canEditStructure(me?.role ?? null);
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const famille = params.get("famille") ?? "";
  const ordering = params.get("ordering") ?? "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [search, setSearch] = useState(q);

  const query: ProcessParams = {
    q: q || undefined,
    famille: (famille as FamilleProcessus) || undefined,
    ordering: ordering || undefined,
    page,
    page_size: PAGE_SIZE,
  };
  const { data, isLoading, isError, refetch } = useProcesses(query);

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  }

  const filtered = q !== "" || famille !== "";
  const createButton = editable && (
    <Button asChild>
      <Link to="nouveau">
        <Plus aria-hidden />
        {s.createProcess}
      </Link>
    </Button>
  );

  const empty = filtered ? (
    <EmptyState title={s.processNoMatch} description={s.processNoMatchHelp} illustration={false} />
  ) : editable ? (
    <EmptyState title={s.processEmptyEditorTitle} description={s.processEmptyEditorHelp}>
      {createButton}
    </EmptyState>
  ) : (
    <EmptyState title={s.processEmptyReaderTitle} />
  );

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{fr.referentiel.pageProcessusList}</h2>
        <div className="print:hidden">{createButton}</div>
      </div>

      <form
        role="search"
        className="flex flex-wrap items-end gap-3 print:hidden"
        onSubmit={(e) => {
          e.preventDefault();
          update({ q: search.trim() });
        }}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="proc-q">{s.processSearch}</Label>
          <Input
            id="proc-q"
            type="search"
            value={search}
            placeholder={s.processSearchPlaceholder}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="proc-famille">{s.familyFilter}</Label>
          <select
            id="proc-famille"
            className={SELECT_CLASS}
            value={famille}
            onChange={(e) => update({ famille: e.target.value })}
          >
            <option value="">{s.allFamilies}</option>
            {FAMILIES.map((f) => (
              <option key={f} value={f}>
                {FAMILLE_LABELS[f]}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" variant="outline">
          {fr.common.search}
        </Button>
      </form>

      {isError ? (
        <div role="alert" className={ALERT_CLASS}>
          <p>{s.loadError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => void refetch()}
          >
            {fr.common.retry}
          </Button>
        </div>
      ) : (
        <DataTable
          caption={s.processListCaption}
          columns={COLUMNS}
          data={data?.results ?? []}
          total={data?.count ?? 0}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) => update({ page: String(p) })}
          ordering={ordering}
          onOrderingChange={(o) => update({ ordering: o })}
          isLoading={isLoading}
          empty={empty}
        />
      )}
    </div>
  );
}
