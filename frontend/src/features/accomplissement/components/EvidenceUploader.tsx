import { useRef, useState, type FormEvent } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { useUploadEvidence } from "../api";

const t = fr.accomplissement.evidence;

type Props = { ficheId: string; missionId: string; disabled?: boolean };
type Errors = { fichier?: string; libelle?: string; general?: string };

/** Dépôt d'une pièce justificative : libellé obligatoire, progression annoncée, envoi annulable. */
export function EvidenceUploader({ ficheId, missionId, disabled = false }: Props) {
  const upload = useUploadEvidence();
  const [label, setLabel] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [ratio, setRatio] = useState<number | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const controller = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const labelInput = useRef<HTMLInputElement>(null);
  const sending = ratio !== null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    const next: Errors = {};
    if (!file) next.fichier = t.noFile;
    if (!label.trim()) next.libelle = t.noLabel;
    if (next.fichier || next.libelle) {
      setErrors(next);
      (next.fichier ? fileInput : labelInput).current?.focus();
      return;
    }
    setErrors({});
    setRatio(0);
    controller.current = new AbortController();
    try {
      await upload.mutateAsync({
        ficheId,
        missionId,
        file: file as File,
        libelle: label.trim(),
        onProgress: setRatio,
        signal: controller.current.signal,
      });
      setLabel("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (isApiError(error)) {
        const fromServer: Errors = {
          fichier: error.errors.fichier?.join(" "),
          libelle: error.errors.libelle?.join(" "),
        };
        const hasField = Boolean(fromServer.fichier ?? fromServer.libelle);
        setErrors(hasField ? fromServer : { general: error.detail });
        if (hasField) (fromServer.fichier ? fileInput : labelInput).current?.focus();
      } else {
        setErrors({ general: fr.errors.generic });
      }
    } finally {
      setRatio(null);
      controller.current = null;
    }
  }

  return (
    <form onSubmit={submit} noValidate className="grid gap-3 rounded-md border border-border p-4">
      {errors.general && (
        <p role="alert" className={ALERT_CLASS}>
          {errors.general}
        </p>
      )}
      <FormField label={t.file} error={errors.fichier} help={t.accepted}>
        {(props) => (
          <Input
            {...props}
            ref={fileInput}
            type="file"
            disabled={disabled || sending}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        )}
      </FormField>
      <FormField label={t.label} error={errors.libelle} help={t.labelHelp}>
        {(props) => (
          <Input
            {...props}
            ref={labelInput}
            value={label}
            maxLength={200}
            disabled={disabled || sending}
            onChange={(e) => setLabel(e.target.value)}
          />
        )}
      </FormField>
      {sending && (
        <div className="grid gap-1">
          <div
            role="progressbar"
            aria-label={t.progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round((ratio ?? 0) * 100)}
            className="h-2 overflow-hidden rounded-full bg-surface-subtle"
          >
            <div
              className="h-full bg-primary"
              style={{ width: `${Math.round((ratio ?? 0) * 100)}%` }}
            />
          </div>
          <p aria-live="polite" className="text-xs text-text-muted">
            {t.progress} : {Math.round((ratio ?? 0) * 100)} %
          </p>
        </div>
      )}
      <div className="flex gap-2">
        <Button type="submit" disabled={disabled || sending}>
          {t.upload}
        </Button>
        {sending && (
          <Button type="button" variant="outline" onClick={() => controller.current?.abort()}>
            {t.cancel}
          </Button>
        )}
      </div>
    </form>
  );
}
