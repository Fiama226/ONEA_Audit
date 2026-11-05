import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { formatDateTime } from "@/lib/dates";
import { useAuditJournal, type AuditLogEntry, type JournalParams } from "../api";
import { fieldLabel, formatValue, t } from "../textes";

const PAGE_SIZE = 25; // PAGE_SIZE DRF du backend

/** Valeur d'une règle telle que stockée par le journal (JSON en texte), rendue lisible. */
function readable(rule: string, raw: unknown): string {
  if (typeof raw !== "string" || raw === "None") return "—";
  try {
    const parsed: unknown = JSON.parse(
      raw
        .replace(/'/g, '"')
        .replace(/\bTrue\b/g, "true")
        .replace(/\bFalse\b/g, "false"),
    );
    if (parsed && typeof parsed === "object") {
      return Object.entries(parsed as Record<string, unknown>)
        .map(([field, value]) => `${fieldLabel(rule, field)} : ${formatValue(rule, field, value)}`)
        .join(" ; ");
    }
  } catch {
    // valeur non JSON : affichée telle quelle
  }
  return raw;
}

function ruleKey(entry: AuditLogEntry): string | null {
  if (entry.model !== "gouvernance.reglegouvernance") return null;
  return entry.object_repr;
}

function Changes({ entry }: { entry: AuditLogEntry }) {
  const rule = ruleKey(entry);
  const changes = Object.entries(entry.changes as Record<string, unknown>).filter(
    ([field]) => !rule || field === "valeur",
  );
  if (changes.length === 0) return <span className="text-text-muted">—</span>;
  return (
    <ul className="m-0 grid list-none gap-1 p-0">
      {changes.map(([field, change]) => {
        if (!Array.isArray(change)) return <li key={field}>{field}</li>;
        const [before, after] = change as unknown[];
        const show = (v: unknown) =>
          rule ? readable(rule, v) : v === "None" || v === null ? "—" : String(v);
        return (
          <li key={field}>
            {!rule && <span className="text-text-muted">{`${field} : `}</span>}
            <span className="line-through decoration-text-muted/60">{show(before)}</span>
            {" → "}
            <span className="font-medium">{show(after)}</span>
          </li>
        );
      })}
    </ul>
  );
}

export function AuditJournalPage() {
  const { me } = useAuth();
  const isDg = me?.role === "DG";
  const [search, setSearch] = useSearchParams();
  const params: JournalParams = {
    categorie: isDg || search.get("categorie") === "gouvernance" ? "gouvernance" : undefined,
    date_from: search.get("du") ?? undefined,
    date_to: search.get("au") ?? undefined,
    page: Number(search.get("page") ?? "1") || 1,
  };
  const query = useAuditJournal(params);

  function update(key: string, value: string) {
    setSearch(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        if (key !== "page") next.delete("page");
        return next;
      },
      { replace: true },
    );
  }

  const page = params.page ?? 1;
  let body;
  if (query.isError) {
    body = (
      <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        <p>{t.journal.loadError}</p>
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
  } else if (!query.data) {
    body = (
      <div role="status" aria-label={fr.common.loading}>
        <Skeleton className="h-48 w-full" />
      </div>
    );
  } else if (query.data.results.length === 0) {
    body = <p className="text-sm text-text-muted">{t.journal.empty}</p>;
  } else {
    const pages = Math.max(1, Math.ceil(query.data.count / PAGE_SIZE));
    body = (
      <>
        <div className="min-w-0 overflow-x-auto rounded-lg border border-border bg-surface">
          <Table>
            <TableCaption className="sr-only">{t.journal.caption}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>{t.journal.colDate}</TableHead>
                <TableHead>{t.journal.colActor}</TableHead>
                <TableHead>{t.journal.colObject}</TableHead>
                <TableHead>{t.journal.colAction}</TableHead>
                <TableHead>{t.journal.colChanges}</TableHead>
                <TableHead>{t.journal.colReason}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data.results.map((entry) => {
                const rule = ruleKey(entry);
                return (
                  <TableRow key={entry.id} className="align-top">
                    <TableCell className="whitespace-nowrap">
                      {formatDateTime(entry.timestamp)}
                    </TableCell>
                    <TableCell>{entry.actor?.username ?? t.journal.system}</TableCell>
                    <TableCell>{rule ? t.journal.ruleObject(rule) : entry.object_repr}</TableCell>
                    <TableCell>
                      {t.journal.actions[entry.action] ?? entry.action}
                      {entry.affaiblissement && (
                        <span className="block text-xs text-warning-text">
                          {t.journal.weakening}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="min-w-64 text-sm">
                      <Changes entry={entry} />
                    </TableCell>
                    <TableCell className="min-w-48 text-sm">{entry.motif ?? "—"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
        <nav aria-label={t.journal.page(page)} className="flex items-center gap-3 text-sm">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => update("page", String(page - 1))}
          >
            {t.journal.previous}
          </Button>
          <span>{`${t.journal.page(page)} / ${pages}`}</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!query.data.next}
            onClick={() => update("page", String(page + 1))}
          >
            {t.journal.next}
          </Button>
        </nav>
      </>
    );
  }

  return (
    <div className="grid gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{t.journal.title}</h1>
        <p className="mt-1 max-w-[75ch] text-sm text-text-muted">
          {isDg ? t.journal.helpDg : t.journal.help}
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        {!isDg && (
          <FormField label={t.journal.category}>
            {(p) => (
              <NativeSelect
                {...p}
                value={params.categorie ?? ""}
                onChange={(e) => update("categorie", e.target.value)}
              >
                <option value="">{t.journal.allCategories}</option>
                <option value="gouvernance">{t.journal.governance}</option>
              </NativeSelect>
            )}
          </FormField>
        )}
        <FormField label={t.journal.from}>
          {(p) => (
            <Input
              {...p}
              type="date"
              value={params.date_from ?? ""}
              onChange={(e) => update("du", e.target.value)}
            />
          )}
        </FormField>
        <FormField label={t.journal.to}>
          {(p) => (
            <Input
              {...p}
              type="date"
              value={params.date_to ?? ""}
              onChange={(e) => update("au", e.target.value)}
            />
          )}
        </FormField>
      </div>
      {body}
    </div>
  );
}
