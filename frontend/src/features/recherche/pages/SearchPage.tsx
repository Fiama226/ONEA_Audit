import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { MIN_QUERY_LENGTH, useSearch, type TypeResultat } from "../api";
import { SearchResults } from "../components/SearchResults";
import { SEARCH_TYPES, TypeFilter } from "../components/TypeFilter";

export const SEARCH_DEBOUNCE_MS = 250;
const T = fr.rechercheNotifications;

function parseTypes(raw: string | null): TypeResultat[] {
  const wanted = (raw ?? "").split(",");
  return SEARCH_TYPES.filter((t) => wanted.includes(t));
}

function errorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.status === 403) return T.searchForbidden;
    if (error.status === 429 || error.status === 503) return error.detail;
  }
  return T.searchError;
}

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const types = parseTypes(params.get("types"));
  const [input, setInput] = useState(q);
  const pushed = useRef(q);

  // Anti-rebond : la requête de l'URL suit le champ au bout de 250 ms.
  useEffect(() => {
    if (input === pushed.current) return;
    const id = window.setTimeout(() => {
      pushed.current = input;
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (input) next.set("q", input);
          else next.delete("q");
          return next;
        },
        { replace: true },
      );
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [input, setParams]);

  // Navigation externe (champ de l'en-tête) : le champ suit l'URL.
  useEffect(() => {
    if (q !== pushed.current) {
      pushed.current = q;
      setInput(q);
    }
  }, [q]);

  const term = q.trim();
  const search = useSearch(term, types);
  const tooShort = term.length < MIN_QUERY_LENGTH;

  const setTypes = (next: TypeResultat[]) =>
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (next.length) p.set("types", next.join(","));
        else p.delete("types");
        return p;
      },
      { replace: true },
    );

  const submit = (e: FormEvent) => {
    e.preventDefault();
    pushed.current = input;
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (input) p.set("q", input);
        else p.delete("q");
        return p;
      },
      { replace: true },
    );
  };

  let body;
  if (tooShort) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {fr.suivi.searchTooShort}
      </p>
    );
  } else if (search.isError) {
    body = (
      <p role="alert" className="text-sm text-destructive">
        {errorMessage(search.error)}
      </p>
    );
  } else if (search.isPending) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {T.searchLoading}
      </p>
    );
  } else {
    body = <SearchResults response={search.data} />;
  }

  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold tracking-[-0.012em]">{fr.suivi.searchTitle}</h1>
      <form role="search" onSubmit={submit} aria-label={T.searchFieldLabel} className="mb-4">
        <Input
          type="search"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setInput("");
          }}
          aria-label={T.searchFieldLabel}
          placeholder={fr.shell.searchPlaceholder}
          autoComplete="off"
          className="max-w-xl"
        />
      </form>
      <div className="mb-6">
        <TypeFilter value={types} onChange={setTypes} />
      </div>
      <div aria-busy={search.isFetching && !tooShort}>{body}</div>
    </>
  );
}
