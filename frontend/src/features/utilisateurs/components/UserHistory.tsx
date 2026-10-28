import { useState } from "react";
import type { components } from "@/api/schema";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { describeChanges, HISTORY_PAGE_SIZE, useUserHistory } from "../history";

type AuditLog = components["schemas"]["AuditLog"];
const t = fr.utilisateursHistorique;

const ACTION_LABELS: Record<string, string> = {
  create: t.actionCreate,
  update: t.actionUpdate,
  delete: t.actionDelete,
};

const COLUMNS: DataTableColumn<AuditLog>[] = [
  {
    id: "timestamp",
    header: t.date,
    enableSorting: false,
    cell: ({ row }) => formatDateTime(row.original.timestamp),
  },
  {
    id: "actor",
    header: t.author,
    enableSorting: false,
    cell: ({ row }) => row.original.actor?.username ?? t.system,
  },
  {
    id: "action",
    header: t.action,
    enableSorting: false,
    cell: ({ row }) => ACTION_LABELS[row.original.action] ?? row.original.action,
  },
  {
    id: "changes",
    header: t.changes,
    enableSorting: false,
    cell: ({ row }) => (
      <ul className="space-y-0.5 py-1">
        {describeChanges(row.original).map((line) => (
          <li key={line.field}>
            {line.label} : {line.before} <span className="sr-only">{t.becomes}</span>
            <span aria-hidden>→</span> {line.after}
          </li>
        ))}
      </ul>
    ),
  },
];

export function UserHistory({ userId }: { userId: number }) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useUserHistory(userId, page);

  return (
    <section aria-labelledby="user-history-title" className="space-y-3">
      <h2 id="user-history-title" className="text-lg font-semibold">
        {t.title}
      </h2>
      {isError ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm"
        >
          <p>{fr.errors.generic}</p>
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
          caption={t.caption}
          columns={COLUMNS}
          data={data?.results ?? []}
          total={data?.count ?? 0}
          page={page}
          pageSize={HISTORY_PAGE_SIZE}
          onPageChange={setPage}
          isLoading={isLoading}
          empty={<EmptyState title={t.empty} illustration={false} />}
        />
      )}
    </section>
  );
}
