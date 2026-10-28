import { useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/auth/useAuth";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fr } from "@/i18n/fr";
import { useDeleteDirection, useDirections } from "../api";
import { ConfirmDeleteDialog } from "../components/ConfirmDeleteDialog";
import { DirectionFormDialog } from "../components/DirectionFormDialog";
import { ALERT_CLASS } from "../components/FormField";
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
  const { data, isLoading, isError, refetch } = useDirections({ page_size: 500 });
  const remove = useDeleteDirection();
  const [form, setForm] = useState<{ direction?: Direction } | null>(null);
  const [toDelete, setToDelete] = useState<Direction | null>(null);

  const all = useMemo(() => data?.results ?? [], [data]);
  const rows = useMemo(() => toRows(all), [all]);
  const parents = useMemo(() => all.filter((d) => d.type === "DIRECTION"), [all]);

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
      <EmptyState
        title={editable ? s.directionsEmptyEditor : s.directionsEmptyReader}
        illustration={false}
      >
        {addButton}
      </EmptyState>
    );
  } else {
    body = (
      <div className="rounded-lg border border-border bg-surface">
        <Table>
          <TableCaption className="sr-only">{s.directionsCaption}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">{fr.referentiel.code}</TableHead>
              <TableHead scope="col">{fr.referentiel.libelle}</TableHead>
              <TableHead scope="col">{fr.referentiel.type}</TableHead>
              {editable && (
                <TableHead scope="col" className="print:hidden">
                  {s.actionsColumn}
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(({ entity, depth }) => (
              <TableRow key={entity.id}>
                <TableCell className={depth === 1 ? "pl-10" : "font-medium"}>
                  {entity.code}
                </TableCell>
                <TableCell>{entity.libelle}</TableCell>
                <TableCell>{TYPE_ENTITE_LABELS[entity.type]}</TableCell>
                {editable && (
                  <TableCell className="print:hidden">
                    <div className="flex gap-1">
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
                        onClick={() => setToDelete(entity)}
                      >
                        <Trash2 aria-hidden />
                      </Button>
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{fr.referentiel.pageDirections}</h2>
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
          open
          onOpenChange={(open) => !open && setToDelete(null)}
          title={s.deleteEntityTitle}
          description={`${toDelete.code} - ${toDelete.libelle}. ${s.deleteEntityText}`}
          onConfirm={() => remove.mutateAsync(toDelete.id)}
        />
      )}
    </div>
  );
}
