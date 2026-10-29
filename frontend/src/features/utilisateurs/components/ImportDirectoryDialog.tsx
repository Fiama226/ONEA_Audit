import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { isApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";
import { useDirectorySearch, useImportDirectory } from "../api";
import type { RapportImport } from "../types";
import { ImportReport } from "./ImportReport";

const t = fr.utilisateurs.import;

const MAX_SELECTION = 50;
const DEBOUNCE_MS = 300;
const ALERT_CLASS = "rounded-md border border-destructive/40 p-3 text-sm text-destructive";

type Props = { open: boolean; onOpenChange: (open: boolean) => void };

export function ImportDirectoryDialog({ open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DirectoryImport onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function errorMessage(error: unknown): string {
  if (isApiError(error) && error.status === 503) return t.directoryUnavailable;
  if (isApiError(error)) return error.detail;
  return fr.errors.generic;
}

function DirectoryImport({ onClose }: { onClose: () => void }) {
  const [input, setInput] = useState("");
  const [term, setTerm] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [limitReached, setLimitReached] = useState(false);
  const [report, setReport] = useState<RapportImport | null>(null);
  const search = useDirectorySearch(term);
  const importer = useImportDirectory();

  useEffect(() => {
    const timer = setTimeout(() => setTerm(input), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [input]);

  const results = term.trim().length >= 2 ? (search.data ?? []) : [];

  function toggle(id: string, checked: boolean) {
    if (!checked) {
      setLimitReached(false);
      setSelected((s) => s.filter((x) => x !== id));
    } else if (selected.length >= MAX_SELECTION) {
      setLimitReached(true);
    } else {
      setSelected((s) => [...s, id]);
    }
  }

  async function submit() {
    importer.reset();
    try {
      setReport(await importer.mutateAsync({ keycloak_ids: selected }));
    } catch {
      // affiché via importer.error
    }
  }

  if (report) {
    return (
      <>
        <DialogHeader>
          <DialogTitle>{t.directoryTitle}</DialogTitle>
          <DialogDescription className="sr-only">{t.directoryHelp}</DialogDescription>
        </DialogHeader>
        <ImportReport report={report} />
        <DialogFooter>
          <Button type="button" onClick={onClose}>
            {t.close}
          </Button>
        </DialogFooter>
      </>
    );
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>{t.directoryTitle}</DialogTitle>
        <DialogDescription>{t.directoryHelp}</DialogDescription>
      </DialogHeader>
      <div className="grid gap-1.5">
        <Label htmlFor="directory-search">{t.searchLabel}</Label>
        <Input
          id="directory-search"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          autoComplete="off"
          aria-describedby="directory-search-hint"
        />
        <p id="directory-search-hint" className="text-xs text-text-muted">
          {t.searchHint}
        </p>
      </div>
      {search.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {errorMessage(search.error)}
        </p>
      )}
      {search.isFetching && (
        <p role="status" className="text-sm text-text-muted">
          {t.searching}
        </p>
      )}
      {search.isSuccess && results.length === 0 && (
        <p className="text-sm text-text-muted">{t.noResult}</p>
      )}
      {results.length > 0 && (
        <div className="max-h-72 overflow-auto rounded-md border border-border">
          <Table>
            <TableCaption className="sr-only">{t.resultsCaption}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">{t.colSelect}</TableHead>
                <TableHead scope="col">{t.colName}</TableHead>
                <TableHead scope="col">{t.colUsername}</TableHead>
                <TableHead scope="col">{t.colEmail}</TableHead>
                <TableHead scope="col">{t.colDirection}</TableHead>
                <TableHead scope="col">{t.colFunction}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((entry) => {
                const present = entry.compte_id !== null;
                return (
                  <TableRow key={entry.keycloak_id}>
                    <TableCell>
                      {present ? (
                        <div className="flex items-center gap-2">
                          <Checkbox
                            disabled
                            checked={false}
                            aria-label={`${t.select} ${entry.nom_complet}`}
                          />
                          <Link
                            to={`/administration/utilisateurs/${entry.compte_id}`}
                            className="text-xs underline"
                          >
                            {t.alreadyPresent}
                          </Link>
                        </div>
                      ) : (
                        <Checkbox
                          checked={selected.includes(entry.keycloak_id)}
                          onCheckedChange={(c) => toggle(entry.keycloak_id, c === true)}
                          aria-label={`${t.select} ${entry.nom_complet}`}
                        />
                      )}
                    </TableCell>
                    <TableCell>{entry.nom_complet}</TableCell>
                    <TableCell>{entry.username}</TableCell>
                    <TableCell>{entry.email}</TableCell>
                    <TableCell>{entry.direction}</TableCell>
                    <TableCell>{entry.fonction}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
      <p role="status" className="text-sm">
        {selected.length} / {MAX_SELECTION} {t.selectedCount}
        {limitReached && (
          <span className="ml-2 font-medium text-destructive">{t.maxSelection}</span>
        )}
      </p>
      {importer.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {errorMessage(importer.error)}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          {fr.common.cancel}
        </Button>
        <Button
          type="button"
          disabled={selected.length === 0 || importer.isPending}
          onClick={() => void submit()}
        >
          {importer.isPending ? t.importing : t.importSelection}
        </Button>
      </DialogFooter>
    </>
  );
}
