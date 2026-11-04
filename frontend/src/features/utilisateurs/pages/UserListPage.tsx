import { Link, useSearchParams } from "react-router-dom";
import { useAccountRights, type AccountRights } from "@/auth/useAccountRights";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useDirectionOptions, useUserAccounts, type UserAccountParams } from "../api";
import { UserListActions } from "../components/UserListActions";
import { SEARCH_MAX_LENGTH, UserFilters, type UserFilterValues } from "../components/UserFilters";
import { UserStatusBadge } from "../components/UserStatusBadge";
import { directionLabel, ROLE_LABELS } from "../labels";
import type { CompteUtilisateurListe, Role } from "../types";

const PAGE_SIZE = 25;
const DEFAULT_ORDERING = "last_name";
const t = fr.utilisateurs.liste;

const ROLES = Object.keys(ROLE_LABELS);
const STATUSES = ["actif", "inactif", "attente"];
const SORTABLE = ["last_name", "role", "direction_code", "is_active", "date_joined"];

/** Valeur d'URL retenue si elle appartient à la liste, sinon vide (jamais envoyée à l'API). */
function oneOf(value: string | null, allowed: string[]): string {
  return value !== null && allowed.includes(value) ? value : "";
}

const FILTER_KEYS = ["q", "role", "statut", "direction"] as const;

const columns: DataTableColumn<CompteUtilisateurListe>[] = [
  {
    id: "last_name",
    header: t.colName,
    cell: ({ row }) => (
      <div>
        <Link
          to={`/administration/utilisateurs/${row.original.id}`}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          {row.original.nom_complet}
        </Link>
        <div className="text-xs text-text-muted">{row.original.username}</div>
      </div>
    ),
  },
  {
    id: "role",
    header: t.colRole,
    cell: ({ row }) => ROLE_LABELS[row.original.role],
  },
  {
    id: "direction_code",
    header: t.colDirection,
    cell: ({ row }) => directionLabel(row.original.direction_code, row.original.direction_libelle),
  },
  {
    id: "fonction",
    header: t.colFunction,
    enableSorting: false,
    cell: ({ row }) => row.original.fonction || t.noValue,
  },
  {
    id: "is_active",
    header: t.colStatus,
    cell: ({ row }) => (
      <UserStatusBadge
        active={row.original.is_active}
        pendingFirstLogin={row.original.en_attente_connexion}
      />
    ),
  },
  {
    id: "date_joined",
    header: t.colCreated,
    cell: ({ row }) => formatDate(row.original.date_joined),
  },
];

/** Traduit les valeurs d'URL en paramètres d'API. */
function toApiParams(f: UserFilterValues, page: number, ordering: string): UserAccountParams {
  const params: UserAccountParams = { page, ordering };
  if (f.q) params.q = f.q;
  if (f.role) params.role = f.role as Role;
  if (f.statut === "actif") params.is_active = true;
  if (f.statut === "inactif") params.is_active = false;
  if (f.statut === "attente") params.en_attente_connexion = true;
  if (f.direction) params.direction_code = f.direction;
  return params;
}

/** Texte de la liste vide : ne mentionne que les actions affichées (UserListActions). */
function emptyText({ isAdmin, rights }: AccountRights): string {
  if (isAdmin) return t.emptyText;
  return rights.creer ? t.emptyTextCreate : t.emptyTextNone;
}

export function UserListPage() {
  const accountRights = useAccountRights();
  const [search, setSearch] = useSearchParams();
  const filters: UserFilterValues = {
    q: (search.get("q") ?? "").trim().slice(0, SEARCH_MAX_LENGTH),
    role: oneOf(search.get("role"), ROLES),
    statut: oneOf(search.get("statut"), STATUSES),
    direction: search.get("direction") ?? "",
  };
  const rawPage = Number(search.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
  const rawOrdering = search.get("ordering") ?? "";
  const ordering = SORTABLE.includes(rawOrdering.replace(/^-/, ""))
    ? rawOrdering
    : DEFAULT_ORDERING;
  const hasFilters = FILTER_KEYS.some((k) => filters[k] !== "");

  const query = useUserAccounts(toApiParams(filters, page, ordering));
  const directions = useDirectionOptions();
  const accounts = query.data?.results ?? [];

  function update(changes: Record<string, string>, keepPage = false) {
    setSearch((prev) => {
      const next = new URLSearchParams(prev);
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      if (!keepPage) next.delete("page");
      return next;
    });
  }

  function clearFilters() {
    setSearch((prev) => {
      const next = new URLSearchParams(prev);
      for (const key of [...FILTER_KEYS, "page"]) next.delete(key);
      return next;
    });
  }

  let body;
  if (query.isError) {
    body = (
      <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        <p>{t.loadError}</p>
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
        caption={t.caption}
        columns={columns}
        data={accounts}
        total={query.data?.count ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={(next) => update({ page: String(next) }, true)}
        ordering={ordering}
        onOrderingChange={(next) =>
          update({ ordering: next === "" || next === DEFAULT_ORDERING ? "" : next }, true)
        }
        isLoading={query.isLoading}
        empty={
          hasFilters ? (
            <EmptyState title={t.emptyFiltered} illustration={false}>
              <Button type="button" variant="outline" onClick={clearFilters}>
                {t.clearFilters}
              </Button>
            </EmptyState>
          ) : (
            <EmptyState
              title={t.emptyTitle}
              description={emptyText(accountRights)}
              illustration={false}
            />
          )
        }
      />
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{fr.utilisateurs.title}</h1>
          <p className="mt-1 max-w-[70ch] text-sm text-text-muted">
            {fr.utilisateurs.directoryNote}
          </p>
        </div>
        <div className="print:hidden">
          <UserListActions />
        </div>
      </div>
      <UserFilters
        values={filters}
        directions={directions.options}
        onChange={(next) => update(next)}
      />
      <p role="status" aria-live="polite" className="sr-only">
        {query.data
          ? `${query.data.count} ${query.data.count === 1 ? fr.table.result : fr.table.results}`
          : ""}
      </p>
      {body}
    </div>
  );
}
