import { useMemo, useRef, useState } from "react";
import { CornerDownRight, Pencil, Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/auth/useAuth";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { fr } from "@/i18n/fr";
import { useAllDirections } from "../allPages";
import { useDeleteDirection } from "../api";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { DirectionFormDialog } from "../components/DirectionFormDialog";
import { ALERT_CLASS } from "../components/FormField";
import { ListIncompleteAlert } from "../components/ListIncompleteAlert";
import { TYPE_ENTITE_LABELS } from "../labels";
import { canEditStructure } from "../permissions";
import type { Direction } from "../types";

const s = fr.refStructure;

type Row = { entity: Direction; depth: 0 | 1 };

/** Directions triées, chacune suivie de ses départements ; les orphelins viennent à la fin. */
function toRows(all: Direction[]): Row[] {
  const byCode = (a: Direction, b: Direction) => a.code.localeCompare(b.code);
  const roots = all.filter((d) => !d.parent).sort(byCode);
  const ids = new Set(all.map((d) => d.id));
  const rows: Row[] = [];
  for (const root of roots) {
    rows.push({ entity: root, depth: 0 });
    for (const child of all.filter((d) => d.parent === root.id).sort(byCode)) {
      rows.push({ entity: child, depth: 1 });
    }
  }
  for (const orphan of all.filter((d) => d.parent && !ids.has(d.parent)).sort(byCode)) {
    rows.push({ entity: orphan, depth: 1 });
  }
  return rows;
}

export function DirectionsPage() {
  const { me } = useAuth();
  const editable = canEditStructure(me?.role ?? null);
  const { data, isLoading, isError, refetch } = useAllDirections();
  const remove = useDeleteDirection();
  const [form, setForm] = useState<{ direction?: Direction } | null>(null);
  const [toDelete, setToDelete] = useState<Direction | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);

  const all = useMemo(() => data?.results ?? [], [data]);
  const rows = useMemo(() => toRows(all), [all]);
  const parents = useMemo(() => all.filter((d) => d.type === "DIRECTION"), [all]);

  const columns = useMemo<DataTableColumn<Row>[]>(() => {
    const cols: DataTableColumn<Row>[] = [
      {
        id: "code",
        header: fr.referentiel.code,
        enableSorting: false,
        cell: ({ row }) => {
          const { entity, depth } = row.original;
          return (
            <span className={depth === 1 ? "inline-flex items-center gap-1.5 pl-5" : "font-medium"}>
              {depth === 1 && <CornerDownRight className="size-3.5 text-text-muted" aria-hidden />}
              {entity.code}
              {entity.parent_code && (
                <span className="sr-only">
                  {" "}
                  {s.attachedTo} {entity.parent_code}
                </span>
              )}
            </span>
          );
        },
      },
      {
        id: "libelle",
        header: fr.referentiel.libelle,
        enableSorting: false,
        cell: ({ row }) => (
          <span className={row.original.depth === 1 ? "pl-5" : "font-medium"}>
            {row.original.entity.libelle}
          </span>
        ),
      },
      {
        id: "type",
        header: fr.referentiel.type,
        enableSorting: false,
        cell: ({ row }) => TYPE_ENTITE_LABELS[row.original.entity.type],
      },
    ];
    if (editable) {
      cols.push({
        id: "actions",
        header: s.actionsColumn,
        enableSorting: false,
        cell: ({ row }) => {
          const { entity } = row.original;
          return (
            <div className="flex gap-1 print:hidden">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`${s.editEntity} ${entity.code}`}
                onClick={() => setForm({ direction: entity })}
              >
                <Pencil aria-hidden />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`${s.deleteEntity} ${entity.code}`}
                onClick={() => {
                  setToDelete(entity);
                  setDeleteOpen(true);
                }}
              >
                <Trash2 aria-hidden />
              </Button>
            </div>
          );
        },
      });
    }
    return cols;
  }, [editable]);

  const addButton = editable && (
    <Button type="button" onClick={() => setForm({})}>
      <Plus aria-hidden />
      {s.addEntity}
    </Button>
  );

  let body;
  if (isLoading) {
    body = <Skeleton role="status" aria-label={fr.common.loading} className="h-48 w-full" />;
  } else if (isError) {
    body = (
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
    );
  } else if (rows.length === 0) {
    body = (
      <EmptyState title={editable ? s.directionsEmptyEditor : s.directionsEmptyReader}>
        {addButton}
      </EmptyState>
    );
  } else {
    body = (
      <>
        {data && <ListIncompleteAlert count={data.count} loaded={all.length} />}
        <DataTable
          caption={s.directionsCaption}
          columns={columns}
          data={rows}
          total={rows.length}
          page={1}
          pageSize={rows.length}
          onPageChange={() => {}}
          isLoading={false}
          empty={null}
        />
      </>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold outline-none">
          {fr.referentiel.pageDirections}
        </h2>
        {rows.length > 0 && <div className="print:hidden">{addButton}</div>}
      </div>
      {body}
      {editable && form && (
        <DirectionFormDialog
          open
          onOpenChange={(open) => !open && setForm(null)}
          direction={form.direction}
          parents={parents}
        />
      )}
      {toDelete && (
        <ConfirmDeleteDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          title={s.deleteEntityTitle}
          description={`${toDelete.code} - ${toDelete.libelle}. ${s.deleteEntityText}`}
          onConfirm={() => remove.mutateAsync(toDelete.id)}
          restoreFocus={() => heading.current?.focus()}
        />
      )}
    </div>
  );
}
