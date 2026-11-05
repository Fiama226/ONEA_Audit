import { Download } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
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
  // Verrou : envoi en cours, ou fichier des mots de passe ni téléchargé ni disparu. Seuls les
  // boutons explicites ferment alors la fenêtre (ni Échap, ni clic à l'extérieur) : le fichier
  // ne se perd pas par mégarde (comme pour « Nouvel agent »).
  const [locked, setLocked] = useState(false);
  const guard = (event: Event) => {
    if (locked) event.preventDefault();
  };
  return (
    <Dialog open={open} onOpenChange={(next) => (next || !locked) && onOpenChange(next)}>
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-2xl"
        onEscapeKeyDown={guard}
        onPointerDownOutside={guard}
        onInteractOutside={guard}
      >
        <CsvImport onLockChange={setLocked} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

type PasswordFileState = "ready" | "busy" | "done" | "gone" | "error";

function errorMessage(error: unknown): string {
  if (!isApiError(error)) return fr.errors.generic;
  const fields = Object.values(error.errors).flat();
  return fields.length > 0 ? fields.join(" ") : error.detail;
}

function CsvImport({
  onClose,
  onLockChange,
}: {
  onClose: () => void;
  onLockChange: (locked: boolean) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  /** Fichier dont la vérification à blanc a réussi : seul celui-là peut être importé. */
  const [verified, setVerified] = useState<File | null>(null);
  const [report, setReport] = useState<RapportImport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sendEmail, setSendEmail] = useState(true);
  const [passwordFile, setPasswordFile] = useState<PasswordFileState>("ready");
  const [confirmClose, setConfirmClose] = useState(false);
  const sendEmailHelp = useId();
  const backRef = useRef<HTMLButtonElement>(null);
  const mutation = useImportCsv();

  const busy = useRef(false);
  const pending = mutation.isPending;
  // Fichier des mots de passe encore téléchargeable : le perdre imposerait de réinitialiser
  // un par un les comptes concernés.
  const passwordsPending =
    Boolean(report?.fichier_mots_de_passe_id) && passwordFile !== "done" && passwordFile !== "gone";
  const locked = pending || passwordsPending;
  useEffect(() => onLockChange(locked), [locked, onLockChange]);
  const confirming = confirmClose && passwordsPending;
  useEffect(() => {
    // Avertissement affiché : le focus va au choix sûr (revenir au téléchargement).
    if (confirming) backRef.current?.focus();
  }, [confirming]);

  function requestClose() {
    if (passwordsPending) setConfirmClose(true);
    else onClose();
  }

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
      // Le cache des mutations ne garde pas le rapport (identifiant du fichier des mots de passe).
      mutation.reset();
      setPasswordFile("ready");
      setConfirmClose(false);
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
  const canImport = file !== null && verified === file && !pending;

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
            disabled={pending}
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
              disabled={pending}
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
      {pending && (
        <p role="status" className="text-sm text-text-muted">
          {t.csvVerifying}
        </p>
      )}
      {report && <ImportReport report={report} />}
      {report?.fichier_mots_de_passe_id && (
        <PasswordFile
          fileId={report.fichier_mots_de_passe_id}
          state={passwordFile}
          onStateChange={setPasswordFile}
        />
      )}
      {!done && !canImport && <p className="text-xs text-text-muted">{t.csvVerifyFirst}</p>}
      {confirming ? (
        <div
          role="alert"
          className="grid gap-3 rounded-md border border-destructive/40 p-3 text-sm"
        >
          <p className="text-destructive">{t.passwordsCloseWarning}</p>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              ref={backRef}
              type="button"
              variant="outline"
              onClick={() => setConfirmClose(false)}
            >
              {t.passwordsCloseBack}
            </Button>
            <Button type="button" variant="destructive" onClick={onClose}>
              {t.passwordsCloseAnyway}
            </Button>
          </div>
        </div>
      ) : (
        <DialogFooter>
          <Button type="button" variant="outline" disabled={pending} onClick={requestClose}>
            {done ? t.close : fr.common.cancel}
          </Button>
          {!done && (
            <>
              <Button
                type="button"
                variant="outline"
                disabled={file === null || pending}
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
      )}
    </>
  );
}

/**
 * Fichier des mots de passe temporaires non partis par courriel : téléchargeable une seule
 * fois (le serveur le détruit aussitôt, 404 ensuite). Le bouton disparaît après le succès.
 * L'état est tenu par le parent : il verrouille la fenêtre tant que le fichier est à prendre.
 */
function PasswordFile({
  fileId,
  state,
  onStateChange,
}: {
  fileId: string;
  state: PasswordFileState;
  onStateChange: (state: PasswordFileState) => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function download() {
    onStateChange("busy");
    setError(null);
    try {
      await downloadImportPasswords(fileId);
      onStateChange("done");
    } catch (e) {
      if (isApiError(e) && e.status === 404) {
        onStateChange("gone");
      } else {
        onStateChange("error");
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
