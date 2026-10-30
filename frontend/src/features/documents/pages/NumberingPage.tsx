import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { isApiError } from "@/api/errors";
import { useAuth } from "@/auth/useAuth";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
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
import {
  useDocumentTypes,
  useNumberingFormats,
  useNumberingPreview,
  useUpdateNumberingFormat,
} from "../api";
import { AdminTabs } from "../components/AdminTabs";
import {
  ABBREVIATION_MAX_LENGTH,
  MODEL_MAX_LENGTH,
  numberingSchema,
  type NumberingFormValues,
} from "../schemas/numbering";
import type { FormatNumerotation } from "../types";

const t = fr.documentsAdmin;
const DEBOUNCE_MS = 300;
const FIELDS = ["modele", "portee", "abreviation"] as const;
type FieldName = (typeof FIELDS)[number];

function isField(name: string): name is FieldName {
  return (FIELDS as readonly string[]).includes(name);
}

export function NumberingPage() {
  const query = useNumberingFormats();
  const types = useDocumentTypes();
  const { me } = useAuth();
  const isAdmin = me?.role === "ADMIN";
  const [editing, setEditing] = useState<FormatNumerotation | null>(null);
  const labels = new Map((types.data ?? []).map((x) => [x.code, x.libelle]));
  const labelOf = (f: FormatNumerotation) => labels.get(f.type_document) ?? f.type_document;

  let body;
  if (query.isError) {
    body = (
      <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
        <p>{t.numberingLoadError}</p>
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
      <div role="status" aria-label={fr.common.loading}>
        <Skeleton className="h-32 w-full" />
      </div>
    );
  } else {
    body = (
      <Table>
        <TableCaption className="sr-only">{t.numberingCaption}</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>{t.colDocument}</TableHead>
            <TableHead>{t.colModel}</TableHead>
            <TableHead>{t.colScope}</TableHead>
            <TableHead>{t.colAbbreviation}</TableHead>
            <TableHead>{t.colPreview}</TableHead>
            {isAdmin && (
              <TableHead>
                <span className="sr-only">{fr.common.actions}</span>
              </TableHead>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {(query.data ?? []).map((f) => (
            <TableRow key={f.type_document}>
              <TableCell>{labelOf(f)}</TableCell>
              <TableCell>
                <code className="font-mono text-xs">{f.modele}</code>
              </TableCell>
              <TableCell>{t.scopes[f.portee] ?? f.portee}</TableCell>
              <TableCell>{f.abreviation}</TableCell>
              <TableCell>{f.apercu ?? "—"}</TableCell>
              {isAdmin && (
                <TableCell>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    aria-label={t.editFormatFor(labelOf(f))}
                    onClick={() => setEditing(f)}
                  >
                    {t.editFormat}
                  </Button>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  return (
    <div className="grid gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{t.numberingTitle}</h1>
        <p className="mt-1 max-w-[70ch] text-sm text-text-muted">{t.numberingHelp}</p>
      </div>
      <AdminTabs />
      {body}
      {editing && (
        <EditFormatDialog
          format={editing}
          label={labelOf(editing)}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function EditFormatDialog({
  format,
  label,
  onClose,
}: {
  format: FormatNumerotation;
  label: string;
  onClose: () => void;
}) {
  const update = useUpdateNumberingFormat();
  const preview = useNumberingPreview();
  const [error, setError] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [previewState, setPreviewState] = useState<{
    /** Saisie (modèle|portée|abréviation) à laquelle l'aperçu et ses erreurs se rapportent. */
    key: string;
    numero: string | null;
    errors: Record<string, string[]>;
    failed: boolean;
    pending: boolean;
  }>({
    key: `${format.modele}|${format.portee}|${format.abreviation}`,
    numero: format.apercu,
    errors: {},
    failed: false,
    pending: false,
  });
  const requestId = useRef(0);
  const {
    register,
    handleSubmit,
    control,
    setFocus,
    formState: { errors },
  } = useForm<NumberingFormValues>({
    resolver: zodResolver(numberingSchema),
    defaultValues: {
      modele: format.modele,
      portee: format.portee,
      abreviation: format.abreviation,
    },
  });
  const values = useWatch({ control });
  const { modele, portee, abreviation } = values;

  const { mutateAsync: runPreview } = preview;
  useEffect(() => {
    if (modele === undefined || portee === undefined || abreviation === undefined) return;
    if (!modele.trim() || !abreviation.trim() || modele.length > MODEL_MAX_LENGTH) return;
    if (abreviation.length > ABBREVIATION_MAX_LENGTH) return;
    const id = ++requestId.current;
    const abort = new AbortController();
    const key = `${modele.trim()}|${portee}|${abreviation.trim()}`;
    const timer = setTimeout(() => {
      setPreviewState((s) => ({ ...s, pending: true }));
      runPreview({
        modele: modele.trim(),
        portee,
        abreviation: abreviation.trim(),
        signal: abort.signal,
      }).then(
        (r) => {
          if (id === requestId.current)
            setPreviewState({
              key,
              numero: r.numero,
              errors: r.errors,
              failed: false,
              pending: false,
            });
        },
        () => {
          if (id === requestId.current)
            setPreviewState({ key, numero: null, errors: {}, failed: true, pending: false });
        },
      );
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [modele, portee, abreviation, runPreview]);

  async function onSubmit(v: NumberingFormValues) {
    if (update.isPending) return;
    setError(null);
    setServerErrors({});
    try {
      await update.mutateAsync({ typeDocument: format.type_document, data: v });
      onClose();
    } catch (e) {
      if (!isApiError(e)) return setError(fr.errors.generic);
      const found: Partial<Record<FieldName, string>> = {};
      for (const [k, msgs] of Object.entries(e.errors)) {
        if (isField(k) && msgs.length > 0) found[k] = msgs.join(" ");
      }
      const first = FIELDS.find((f) => found[f]);
      if (first) {
        setServerErrors(found);
        setFocus(first);
      } else {
        setError(e.detail);
      }
    }
  }

  // Les erreurs d'aperçu d'une saisie antérieure ne sont plus affichées.
  const currentKey = `${(modele ?? "").trim()}|${portee}|${(abreviation ?? "").trim()}`;
  const previewErrors = previewState.key === currentKey ? previewState.errors : {};
  const fieldError = (name: FieldName): string | undefined =>
    errors[name]?.message ??
    serverErrors[name] ??
    (previewErrors[name]?.length ? previewErrors[name].join(" ") : undefined);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t.editTitle(label)}</DialogTitle>
            <DialogDescription>{t.editDescription}</DialogDescription>
          </DialogHeader>
          {error && (
            <p role="alert" className={ALERT_CLASS}>
              {error}
            </p>
          )}
          <FormField label={t.fieldModel} error={fieldError("modele")}>
            {(p) => <Input {...p} maxLength={MODEL_MAX_LENGTH} {...register("modele")} />}
          </FormField>
          <FormField label={t.fieldScope} error={fieldError("portee")}>
            {(p) => (
              <NativeSelect {...p} {...register("portee")}>
                <option value="MISSION">{t.scopes.MISSION}</option>
                <option value="ANNEE">{t.scopes.ANNEE}</option>
              </NativeSelect>
            )}
          </FormField>
          <FormField label={t.fieldAbbreviation} error={fieldError("abreviation")}>
            {(p) => (
              <Input {...p} maxLength={ABBREVIATION_MAX_LENGTH} {...register("abreviation")} />
            )}
          </FormField>
          <p role="status" className="text-sm">
            <span className="font-medium">{t.previewLabel} : </span>
            {previewState.pending
              ? t.previewPending
              : previewState.failed
                ? t.previewFailed
                : (previewState.numero ?? "—")}
          </p>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              {fr.common.cancel}
            </Button>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? t.savingFormat : t.saveFormat}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
