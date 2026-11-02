import { flexRender, type RowData } from "@tanstack/react-table";
import {
  getCoreRowModel,
  useLegacyTable,
  type LegacyColumnDef,
} from "@tanstack/react-table/legacy";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fr } from "@/i18n/fr";
import { cn } from "@/lib/utils";

export type DataTableColumn<T extends RowData> = LegacyColumnDef<T>;

export type DataTableProps<T extends RowData> = {
  /** Légende accessible du tableau (masquée visuellement). */
  caption: string;
  /**
   * L'`id` de colonne est le champ `ordering` envoyé au serveur : donner un `id` (ou un
   * `accessorKey`) à chaque colonne, et `enableSorting: false` aux colonnes non triables
   * (actions, champs calculés).
   */
  columns: DataTableColumn<T>[];
  data: T[];
  /** Nombre total de lignes côté serveur. */
  total: number;
  /** Page courante, à partir de 1. */
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  /** Tri serveur : `champ` (croissant) ou `-champ` (décroissant). */
  ordering?: string;
  onOrderingChange?: (ordering: string) => void;
  isLoading: boolean;
  /**
   * Affiché à la place du tableau quand il n'y a aucune ligne hors chargement, y compris si la
   * requête a échoué : la page doit traiter `isError` (message d'erreur) avant d'afficher le tableau.
   */
  empty: ReactNode;
  /** Nom du repère de pagination ; à distinguer quand plusieurs tableaux sont sur la même page. */
  paginationLabel?: string;
};

const SKELETON_ROWS = 5;

function nextOrdering(current: string | undefined, id: string): string {
  if (current === id) return `-${id}`;
  if (current === `-${id}`) return "";
  return id;
}

export function DataTable<T extends RowData>({
  caption,
  columns,
  data,
  total,
  page,
  pageSize,
  onPageChange,
  ordering,
  onOrderingChange,
  isLoading,
  empty,
  paginationLabel = fr.table.pagination,
}: DataTableProps<T>) {
  const table = useLegacyTable<T>({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    manualSorting: true,
    rowCount: total,
  });

  if (!isLoading && data.length === 0) return <>{empty}</>;

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const headerGroups = table.getHeaderGroups();
  const colSpan = columns.length;

  return (
    <div className="rounded-lg border border-border bg-surface">
      {/* overflow-x-auto : un tableau plus large que l'écran défile au lieu d'être tronqué (WCAG 1.4.10) ;
          le conteneur est focusable pour le défilement au clavier. */}
      <div
        data-slot="table-container"
        className="overflow-x-auto"
        tabIndex={0}
      >
        <table aria-busy={isLoading} className="w-full caption-bottom text-sm tabular-nums">
          <TableCaption className="sr-only">{caption}</TableCaption>
          <TableHeader className="sticky top-0 z-10 bg-surface-subtle">
            {headerGroups.map((group) => (
              <TableRow key={group.id} className="hover:bg-transparent">
                {group.headers.map((header) => {
                  const id = header.column.id;
                  const sortable =
                    onOrderingChange !== undefined &&
                    header.column.columnDef.enableSorting !== false;
                  const direction =
                    ordering === id
                      ? "ascending"
                      : ordering === `-${id}`
                        ? "descending"
                        : undefined;
                  const content = header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext());
                  return (
                    <TableHead
                      key={header.id}
                      scope="col"
                      aria-sort={sortable ? (direction ?? "none") : undefined}
                      className="h-11 px-4 text-xs font-semibold text-text-muted"
                    >
                      {sortable ? (
                        <button
                          type="button"
                          onClick={() => onOrderingChange(nextOrdering(ordering, id))}
                          className="inline-flex items-center gap-1.5 rounded-sm hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
                        >
                          {content}
                          {direction === "ascending" ? (
                            <ArrowUp className="size-3.5" aria-hidden />
                          ) : direction === "descending" ? (
                            <ArrowDown className="size-3.5" aria-hidden />
                          ) : (
                            <ChevronsUpDown className="size-3.5 opacity-50" aria-hidden />
                          )}
                        </button>
                      ) : (
                        content
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading && data.length === 0
              ? Array.from({ length: SKELETON_ROWS }, (_, row) => (
                  <TableRow key={row} className="h-11">
                    {Array.from({ length: colSpan }, (_, col) => (
                      <TableCell key={col} className="px-4">
                        <Skeleton className="h-4 w-3/4" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : table.getRowModel().rows.map((row) => (
                  <TableRow key={row.id} className="h-11">
                    {row.getAllCells().map((cell) => (
                      <TableCell key={cell.id} className={cn("px-4")}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
          </TableBody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-border px-4 py-2 text-sm text-text-muted print:hidden">
        <span className="tabular-nums">
          {total} {total === 1 ? fr.table.result : fr.table.results}
        </span>
        <nav aria-label={paginationLabel} className="flex items-center gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            {fr.table.previousPage}
          </Button>
          <span className="tabular-nums" aria-live="polite">
            {fr.table.page} {page} {fr.table.of} {pageCount}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => onPageChange(page + 1)}
          >
            {fr.table.nextPage}
          </Button>
        </nav>
      </div>
    </div>
  );
}
