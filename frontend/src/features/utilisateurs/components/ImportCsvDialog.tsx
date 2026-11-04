import { Download } from "lucide-react";
import { useId, useRef, useState } from "react";
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
import { downloadImportPasswords, useImportCsv } from "../api";
import type { RapportImport } from "../types";
import { ImportReport } from "./ImportReport";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.utilisateurs.import;
/** Limite serveur (1 Mo) : inutile d'envoyer un fichier plus gros. */
const MAX_BYTES = 1024 * 1024;
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
  const [sendEmail, setSendEmail] = useState(true);
  const sendEmailHelp = useId();
  const mutation = useImportCsv();

  const busy = useRef(false);

  function onFileChange(next: File | null) {
    setVerified(null);
    setReport(null);
    if (next !== null && next.size > MAX_BYTES) {
      setFile(null);
      setError(t.csvTooLarge);
      return;
    }
    setFile(next);
    setError(null);
  }

  async function run(dryRun: boolean) {
    if (!file || busy.current) return;
    busy.current = true;
    setError(null);
    try {
      const result = await mutation.mutateAsync({ file, dryRun, sendEmail });
      setReport(result);
      setVerified(dryRun ? file : null);
    } catch (e) {
      setReport(null);
      setVerified(null);
      setError(errorMessage(e));
    } finally {
      busy.current = false;
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
        <ScrollRegion label={t.csvExample}>
          <pre className="text-xs">{t.csvExampleText}</pre>
        </ScrollRegion>
      </div>
      {!done && (
        <div className="grid gap-1.5">
          <Label htmlFor="csv-file">{t.csvFile}</Label>
          <Input
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            disabled={mutation.isPending}
            onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          />
        </div>
      )}
      {!done && (
        <div className="grid gap-1">
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              className="size-4 accent-primary"
              checked={sendEmail}
              disabled={mutation.isPending}
              aria-describedby={sendEmailHelp}
              onChange={(e) => setSendEmail(e.target.checked)}
            />
            {t.csvSendEmail}
          </label>
          <p id={sendEmailHelp} className="text-xs text-text-muted">
            {t.csvSendEmailHelp}
          </p>
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
      {report?.fichier_mots_de_passe_id && (
        <PasswordFile fileId={report.fichier_mots_de_passe_id} />
      )}
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

/**
 * Fichier des mots de passe temporaires non partis par courriel : téléchargeable une seule
 * fois (le serveur le détruit aussitôt, 404 ensuite). Le bouton disparaît après le succès.
 */
function PasswordFile({ fileId }: { fileId: string }) {
  const [state, setState] = useState<"ready" | "busy" | "done" | "gone" | "error">("ready");
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setState("busy");
    setError(null);
    try {
      await downloadImportPasswords(fileId);
      setState("done");
    } catch (e) {
      if (isApiError(e) && e.status === 404) {
        setState("gone");
      } else {
        setState("error");
        setError(isApiError(e) ? e.detail : fr.errors.generic);
      }
    }
  }

  return (
    <section
      aria-labelledby={`mots-de-passe-${fileId}`}
      className="grid gap-2 rounded-md border border-warning/50 p-3 text-sm"
    >
      <h4 id={`mots-de-passe-${fileId}`} className="font-semibold">
        {t.passwordsTitle}
      </h4>
      <p>{t.passwordsText}</p>
      {(state === "ready" || state === "busy" || state === "error") && (
        <div>
          <Button type="button" disabled={state === "busy"} onClick={() => void download()}>
            <Download aria-hidden />
            {state === "busy" ? t.passwordsDownloading : t.passwordsDownload}
          </Button>
        </div>
      )}
      <p role="status" className="text-success-text">
        {state === "done" ? t.passwordsDownloaded : ""}
      </p>
      {state === "gone" && (
        <p role="alert" className={ALERT_CLASS}>
          {t.passwordsGone}
        </p>
      )}
      {state === "error" && error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
    </section>
  );
}
