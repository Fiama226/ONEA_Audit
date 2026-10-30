import { useEffect, useRef, useState } from "react";
import { isApiError } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { HashDisplay } from "@/features/documents/components/HashDisplay";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import {
  downloadImplementationEvidence,
  useImplementationEvidence,
  useRemoveImplementationEvidence,
  useUploadImplementationEvidence,
} from "../api";
import { fieldErrorsOf, generalErrorOf } from "../serverErrors";
import type { ActionSuivie, PreuveMiseEnOeuvre } from "../types";

const t = fr.suiviRegistre;

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1).replace(".", ",")} Ko`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} Mo`;
}

type UploadErrors = { libelle?: string; fichier?: string; general?: string };

/** Formulaire de dépôt : libellé, fichier, progression annoncée (aria-live). */
function UploadForm({ actionId }: { actionId: string }) {
  const upload = useUploadImplementationEvidence();
  const [libelle, setLibelle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<UploadErrors>({});
  const [progress, setProgress] = useState<number | null>(null);
  const [done, setDone] = useState(false);
  const [fileKey, setFileKey] = useState(0);
  const labelRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [focus, setFocus] = useState<{ field: "libelle" | "fichier"; n: number } | null>(null);

  useEffect(() => {
    if (focus?.field === "libelle") labelRef.current?.focus();
    if (focus?.field === "fichier") fileRef.current?.focus();
  }, [focus]);

  function fail(next: UploadErrors) {
    setErrors(next);
    const field = next.libelle ? "libelle" : next.fichier ? "fichier" : null;
    if (field) setFocus((previous) => ({ field, n: (previous?.n ?? 0) + 1 }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setDone(false);
    const trimmed = libelle.trim();
    if (!trimmed || !file) {
      fail({
        libelle: trimmed ? undefined : t.evidenceLabelRequired,
        fichier: file ? undefined : t.evidenceFileRequired,
      });
      return;
    }
    setErrors({});
    setProgress(0);
    try {
      await upload.mutateAsync({ actionId, file, libelle: trimmed, onProgress: setProgress });
      setLibelle("");
      setFile(null);
      setFileKey((n) => n + 1);
      setDone(true);
    } catch (error) {
      const fields = fieldErrorsOf(error);
      fail({
        libelle: fields.libelle,
        fichier: fields.fichier,
        general: generalErrorOf(error),
      });
    } finally {
      setProgress(null);
    }
  }

  return (
    <form
      onSubmit={(e) => void submit(e)}
      noValidate
      className="grid gap-3 rounded-md border border-border p-4"
    >
      <FormField label={t.evidenceLabel} error={errors.libelle}>
        {(props) => (
          <Input
            {...props}
            ref={labelRef}
            value={libelle}
            onChange={(e) => setLibelle(e.target.value)}
          />
        )}
      </FormField>
      <FormField label={t.evidenceFile} error={errors.fichier}>
        {(props) => (
          <Input
            {...props}
            key={fileKey}
            ref={fileRef}
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        )}
      </FormField>
      <div>
        <Button type="submit" disabled={upload.isPending}>
          {t.evidenceUpload}
        </Button>
      </div>
      <p aria-live="polite" role="status" className="text-sm text-text-muted">
        {progress !== null
          ? t.evidenceProgress.replace("{pct}", String(Math.round(progress * 100)))
          : done
            ? t.evidenceDone
            : ""}
      </p>
      {errors.general && (
        <p role="alert" className={ALERT_CLASS}>
          {errors.general}
        </p>
      )}
    </form>
  );
}

function EvidenceItem({ preuve, actionId }: { preuve: PreuveMiseEnOeuvre; actionId: string }) {
  const remove = useRemoveImplementationEvidence();
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string>();
  const possible = new Set(preuve.actions_possibles);

  async function download() {
    setError(undefined);
    try {
      await downloadImplementationEvidence(preuve.id, preuve.nom_fichier_original);
    } catch (e) {
      setError(isApiError(e) ? e.detail : t.evidenceDownloadError);
    }
  }

  return (
    <li className="grid gap-1 rounded-md border border-border p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">
          {preuve.numero}. {preuve.libelle}
        </span>
        <span className="flex gap-2">
          {possible.has("TELECHARGER") && (
            <Button
              type="button"
              variant="outline"
              size="xs"
              aria-label={`${t.evidenceDownload} ${preuve.libelle}`}
              onClick={() => void download()}
            >
              {t.evidenceDownload}
            </Button>
          )}
          {possible.has("RETIRER") && (
            <Button
              type="button"
              variant="outline"
              size="xs"
              aria-label={`${t.evidenceRemove} ${preuve.libelle}`}
              onClick={() => setConfirm(true)}
            >
              {t.evidenceRemove}
            </Button>
          )}
        </span>
      </div>
      <p className="text-text-muted">
        {preuve.nom_fichier_original} · {size(preuve.taille_octets)} ·{" "}
        {t.evidenceBy
          .replace("{name}", preuve.deposee_par.nom_complet)
          .replace("{date}", formatDateTime(preuve.deposee_le))}
      </p>
      <p className="flex items-center gap-1 text-xs text-text-muted">
        {t.evidenceHash} : <HashDisplay value={preuve.empreinte_sha256} />
      </p>
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      <ConfirmActionDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t.evidenceRemoveTitle}
        text={t.evidenceRemoveText}
        confirmLabel={t.evidenceRemoveConfirm}
        requireCheck={false}
        onConfirm={() => remove.mutateAsync({ id: preuve.id, actionId })}
      />
    </li>
  );
}

/** Preuves de mise en œuvre : dépôt, liste (empreinte abrégée) et téléchargement authentifié. */
export function EvidencePanel({ action }: { action: ActionSuivie }) {
  const evidence = useImplementationEvidence(action.id);
  const canUpload = action.actions_possibles.includes("DEPOSER_PREUVE");

  return (
    <section
      aria-labelledby="evidence-title"
      className="grid gap-3 rounded-lg border border-border p-5"
    >
      <h2 id="evidence-title" className="text-base font-semibold">
        {t.evidenceTitle}
      </h2>
      {canUpload && <UploadForm actionId={action.id} />}
      {evidence.isError ? (
        <p role="alert" className={ALERT_CLASS}>
          {t.evidenceLoadError}
        </p>
      ) : evidence.isLoading ? (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      ) : evidence.data && evidence.data.results.length > 0 ? (
        <ul className="grid gap-2">
          {evidence.data.results.map((p) => (
            <EvidenceItem key={p.id} preuve={p} actionId={action.id} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-text-muted">{t.evidenceNone}</p>
      )}
    </section>
  );
}
