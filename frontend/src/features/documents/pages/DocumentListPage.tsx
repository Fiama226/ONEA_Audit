import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { useRole } from "@/auth/useRole";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { ALERT_CLASS } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useDocuments, useDocumentTypes, type DocumentParams } from "../api";
import { DocumentStatusBadge } from "../components/DocumentStatusBadge";
import { DOCUMENT_TYPE_LABELS } from "../labels";
import type { DocumentListe } from "../types";

const t = fr.documentsRegistre;
const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;

const LINK_CLASS =
  "font-medium text-primary underline-offset-[3px] hover:underline focus-visible:outline-2 focus-visible:outline-ring";

/** Le nombre de téléchargements n'est pas exposé par la liste : il figure sur la page du document (RAI). */
function makeColumns(): DataTableColumn<DocumentListe>[] {
  return [
    {
      id: "numero",
      header: t.colNumber,
      enableSorting: false,
      cell: ({ row }) => (
        <Link to={row.original.id} className={LINK_CLASS}>
          {row.original.numero}
        </Link>
      ),
    },
    {
      id: "document",
      header: t.colDocument,
      enableSorting: false,
      cell: ({ row }) => row.original.type_document_libelle,
    },
    {
      id: "mission",
      header: t.colMission,
      enableSorting: false,
      cell: ({ row }) => (
        <Link to={`/missions/${row.original.mission.id}`} className={LINK_CLASS}>
          {row.original.mission.reference || row.original.mission.titre}
        </Link>
      ),
    },
    {
      id: "version",
      header: t.colVersion,
      enableSorting: false,
      cell: ({ row }) =>
        row.original.derniere_version ? (
          `v${row.original.derniere_version.numero_version}`
        ) : (
          <span className="text-text-muted">{t.noVersionYet}</span>
        ),
    },
    {
      id: "genere_le",
      header: t.colGeneratedAt,
      enableSorting: false,
      cell: ({ row }) => {
        const at = row.original.derniere_version?.genere_le;
        return at ? formatDateTime(at) : <span className="text-text-muted">—</span>;
      },
    },
    {
      id: "statut",
      header: t.colStatus,
      enableSorting: false,
      cell: ({ row }) =>
        row.original.derniere_version ? (
          <DocumentStatusBadge version={row.original.derniere_version} />
        ) : (
          <span className="text-text-muted">{fr.documents.notGenerated}</span>
        ),
    },
  ];
}

const COLUMNS = makeColumns();

export function DocumentListPage() {
  const { is } = useRole();
  const [params, setParams] = useSearchParams();
  // /document-types/ est réservé à l'ADMIN et au RAI (403 sinon) : les autres rôles ont la liste statique.
  const types = useDocumentTypes(is("RAI"));
  const typeOptions: { code: string; libelle: string }[] =
    types.data ??
    Object.entries(DOCUMENT_TYPE_LABELS).map(([code, libelle]) => ({ code, libelle }));
  const q = (params.get("q") ?? "").slice(0, 100);
  const rawType = params.get("type") ?? "";
  // Une valeur inconnue de l'URL est écartée.
  const type = typeOptions.some((d) => d.code === rawType) ? rawType : "";
  const page = Math.max(1, Math.floor(Number(params.get("page"))) || 1);

  const [search, setSearch] = useState(q);
  const [seenQ, setSeenQ] = useState(q);
  if (q !== seenQ) {
    setSeenQ(q);
    // Ne pas écraser la saisie en cours quand l'URL vient de l'anti-rebond.
    if (q !== search.trim()) setSearch(q);
  }

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  }

  useEffect(() => {
    const trimmed = search.trim().slice(0, 100);
    if (trimmed === q) return;
    const timer = setTimeout(() => {
      const next = new URLSearchParams(params);
      if (trimmed) next.set("q", trimmed);
      else next.delete("q");
      next.delete("page");
      setParams(next, { replace: true });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search, q, params, setParams]);

  const query: DocumentParams = {
    q: q || undefined,
    type_document: type || undefined,
    page,
    page_size: PAGE_SIZE,
  };
  const { data, isLoading, isError, error, refetch } = useDocuments(query);

  // Page hors limites (404) : retour automatique à la première page, URL assainie.
  const outOfRange = isError && page > 1 && isApiError(error) && error.status === 404;
  useEffect(() => {
    if (!outOfRange) return;
    const next = new URLSearchParams(params);
    next.delete("page");
    setParams(next, { replace: true });
  }, [outOfRange, params, setParams]);

  const filtered = q !== "" || type !== "";
  const empty = filtered ? (
    <EmptyState title={t.emptyFiltered} illustration={false} />
  ) : is("AUDITE") ? (
    <EmptyState title={t.emptyAudite} />
  ) : (
    <EmptyState title={t.emptyRai} />
  );

  const total = data?.count ?? 0;

  return (
    <div className="grid gap-4">
      <h1 className="text-2xl font-semibold tracking-[-0.012em]">{t.title}</h1>

      <form
        role="search"
        className="flex flex-wrap items-end gap-3 print:hidden"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="doc-q">{t.searchLabel}</Label>
          <Input
            id="doc-q"
            type="search"
            value={search}
            maxLength={100}
            placeholder={t.searchPlaceholder}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="doc-type">{t.typeLabel}</Label>
          <NativeSelect
            id="doc-type"
            value={type}
            onChange={(e) => update({ type: e.target.value })}
          >
            <option value="">{t.allTypes}</option>
            {typeOptions.map((d) => (
              <option key={d.code} value={d.code}>
                {d.libelle}
              </option>
            ))}
          </NativeSelect>
        </div>
      </form>

      {/* Nombre de résultats annoncé aux lecteurs d'écran à chaque filtrage. */}
      <p role="status" className="sr-only">
        {!isLoading && !isError
          ? `${total} ${total === 1 ? fr.table.result : fr.table.results}`
          : ""}
      </p>

      {isError ? (
        <div role="alert" className={ALERT_CLASS}>
          <p>{t.loadError}</p>
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
        <DataTable<DocumentListe>
          caption={t.listCaption}
          columns={COLUMNS}
          data={data?.results ?? []}
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={(p) => update({ page: String(p) })}
          isLoading={isLoading}
          empty={empty}
        />
      )}
    </div>
  );
}
