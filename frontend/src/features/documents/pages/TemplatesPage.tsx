import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
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
import { formatDate } from "@/lib/dates";
import { useDocumentTypes } from "../api";
import { AdminTabs } from "../components/AdminTabs";

const t = fr.documentsAdmin;

export function TemplatesPage() {
  const query = useDocumentTypes();
  const types = query.data ?? [];
  const provisional = types.filter((x) => x.gabarit_actif?.provisoire).length;

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
  } else if (query.isLoading) {
    body = (
      <div role="status" aria-label={fr.common.loading} className="grid gap-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  } else {
    body = (
      <Table>
        <TableCaption className="sr-only">{t.templatesCaption}</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>{t.colDocument}</TableHead>
            <TableHead>{t.colStep}</TableHead>
            <TableHead>{t.colActive}</TableHead>
            <TableHead>{t.colActivatedAt}</TableHead>
            <TableHead>{t.colContract}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {types.map((type) => {
            const active = type.gabarit_actif;
            return (
              <TableRow key={type.code}>
                <TableCell>
                  <Link
                    to={`/administration/documents/${encodeURIComponent(type.code)}`}
                    className="font-medium text-primary underline-offset-4 hover:underline"
                  >
                    {type.libelle}
                  </Link>
                </TableCell>
                <TableCell>{type.etape_romain ?? "—"}</TableCell>
                <TableCell>
                  {active ? (
                    <span className="inline-flex flex-wrap items-center gap-1">
                      {`v${active.version}`}
                      {active.provisoire && <Badge variant="secondary">{t.provisional}</Badge>}
                    </span>
                  ) : (
                    <span className="text-text-muted">{t.noActive}</span>
                  )}
                </TableCell>
                <TableCell>{active?.active_le ? formatDate(active.active_le) : "—"}</TableCell>
                <TableCell>{`v${type.contrat_version}`}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    );
  }

  return (
    <div className="grid gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{t.templatesTitle}</h1>
        <p className="mt-1 max-w-[70ch] text-sm text-text-muted">{t.templatesIntro}</p>
      </div>
      <AdminTabs />
      {provisional > 0 && (
        <p role="note" className="rounded-md border border-border bg-surface-subtle p-3 text-sm">
          {t.provisionalBanner(provisional)}
        </p>
      )}
      {body}
    </div>
  );
}
