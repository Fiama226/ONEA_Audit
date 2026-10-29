import { useState } from "react";
import { Button } from "@/components/ui/button";
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
import { isApiError } from "@/api/errors";
import { fr } from "@/i18n/fr";
import { useImportCsv } from "../api";
import type { RapportImport } from "../types";
import { ImportReport } from "./ImportReport";

const t = fr.utilisateurs.import;
const ALERT_CLASS = "rounded-md border border-destructive/40 p-3 text-sm text-destructive";

type Props = { open: boolean; onOpenChange: (open: boolean) => void };

export function ImportCsvDialog({ open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <CsvImport onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function errorMessage(error: unknown): string {
  if (!isApiError(error)) return fr.errors.generic;
  const fields = Object.values(error.errors).flat();
  return fields.length > 0 ? fields.join(" ") : error.detail;
}

function CsvImport({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  /** Fichier dont la vérification à blanc a réussi : seul celui-là peut être importé. */
  const [verified, setVerified] = useState<File | null>(null);
  const [report, setReport] = useState<RapportImport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mutation = useImportCsv();

  function onFileChange(next: File | null) {
    setFile(next);
    setVerified(null);
    setReport(null);
    setError(null);
  }

  async function run(dryRun: boolean) {
    if (!file) return;
    setError(null);
    try {
      const result = await mutation.mutateAsync({ file, dryRun });
      setReport(result);
      setVerified(dryRun ? file : null);
    } catch (e) {
      setReport(null);
      setVerified(null);
      setError(errorMessage(e));
    }
  }

  const done = report !== null && !report.dry_run;
  const canImport = file !== null && verified === file && !mutation.isPending;

  return (
    <>
      <DialogHeader>
        <DialogTitle>{t.csvTitle}</DialogTitle>
        <DialogDescription className="sr-only">{t.csvDescription}</DialogDescription>
      </DialogHeader>
      <div className="grid gap-1 rounded-md bg-surface-subtle p-3 text-sm">
        <p className="font-semibold">{t.csvHelpTitle}</p>
        <p>{t.csvColumns}</p>
        <p>{t.csvFormat}</p>
        <p>{t.csvAdmin}</p>
        <p className="font-semibold">{t.csvExample}</p>
        <pre className="overflow-x-auto text-xs">{t.csvExampleText}</pre>
      </div>
      {!done && (
        <div className="grid gap-1.5">
          <Label htmlFor="csv-file">{t.csvFile}</Label>
          <Input
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          />
        </div>
      )}
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      {mutation.isPending && (
        <p role="status" className="text-sm text-text-muted">
          {t.csvVerifying}
        </p>
      )}
      {report && <ImportReport report={report} />}
      {!done && !canImport && <p className="text-xs text-text-muted">{t.csvVerifyFirst}</p>}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          {done ? t.close : fr.common.cancel}
        </Button>
        {!done && (
          <>
            <Button
              type="button"
              variant="outline"
              disabled={file === null || mutation.isPending}
              onClick={() => void run(true)}
            >
              {t.csvVerify}
            </Button>
            <Button type="button" disabled={!canImport} onClick={() => void run(false)}>
              {t.csvImport}
            </Button>
          </>
        )}
      </DialogFooter>
    </>
  );
}
