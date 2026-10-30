import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
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
import { useAuth } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { downloadTemplate, previewTemplate, useDocumentTypes, useTemplateVersions } from "../api";
import { ActivateTemplateDialog } from "../components/ActivateTemplateDialog";
import { ContractFieldsPanel } from "../components/ContractFieldsPanel";
import { UploadTemplateDialog } from "../components/UploadTemplateDialog";
import { STATUT_GABARIT_LABELS } from "../labels";
import type { FormatFichier, Gabarit } from "../types";

const t = fr.documentsAdmin;

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
    : `${Math.max(1, Math.round(bytes / 1024))} Ko`;
}

export function TemplateDetailPage() {
  const { type: rawType } = useParams();
  const types = useDocumentTypes();
  const code = rawType ?? "";
  const type = types.data?.find((x) => x.code === code);
  const templates = useTemplateVersions(code);
  const { me } = useAuth();
  const isAdmin = me?.role === "ADMIN";
  const [uploadOpen, setUploadOpen] = useState(false);
  const [toActivate, setToActivate] = useState<Gabarit | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const running = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const opener = useRef<HTMLElement | null>(null);

  // Aperçu ou téléchargement en cours : annulé quand on quitte la page.
  useEffect(() => () => controller.current?.abort(), []);

  async function run(
    key: string,
    action: (signal: AbortSignal) => Promise<void>,
    fallback: string,
  ) {
    if (running.current) return;
    running.current = true;
    const current = new AbortController();
    controller.current = current;
    setBusy(key);
    setActionError(null);
    try {
      await action(current.signal);
    } catch (e) {
      if (!current.signal.aborted) setActionError(isApiError(e) ? e.detail : fallback);
    } finally {
      running.current = false;
      if (!current.signal.aborted) setBusy(null);
    }
  }

  /** Rend le focus au bouton d'origine, ou au titre si ce bouton a disparu (version devenue active). */
  function restoreFocus(event: Event) {
    event.preventDefault();
    const target = opener.current?.isConnected ? opener.current : heading.current;
    target?.focus();
  }

  const back = (
    <Link
      to="/administration/documents"
      className="text-sm text-primary underline-offset-4 hover:underline"
    >
      {t.back}
    </Link>
  );

  if (types.isError || templates.isError) {
    return (
      <div className="grid gap-3">
        {back}
        <div role="alert" className="rounded-lg border border-border bg-surface p-6 text-sm">
          <h1 className="sr-only">{t.templatesTitle}</h1>
          <p>{t.loadError}</p>
          <Button
            type="button"
            variant="outline"
            className="mt-3"
            onClick={() => {
              void types.refetch();
              void templates.refetch();
            }}
          >
            {fr.common.retry}
          </Button>
        </div>
      </div>
    );
  }
  if (types.isLoading) {
    return (
      <div role="status" aria-label={fr.common.loading} className="grid gap-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (!type) {
    return (
      <div className="grid gap-3">
        {back}
        <h1 className="text-2xl font-semibold">{t.unknownType}</h1>
      </div>
    );
  }

  const versions = templates.data?.results ?? [];
  const restoreAfterUpload = (event: Event) => {
    event.preventDefault();
    heading.current?.focus();
  };

  return (
    <div className="grid gap-6">
      <div className="grid gap-2">
        {back}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 ref={heading} tabIndex={-1} className="text-2xl font-semibold outline-none">
            {`${t.detailTitle}${type.libelle}`}
          </h1>
          {isAdmin && (
            <Button type="button" onClick={() => setUploadOpen(true)}>
              {t.uploadOpen}
            </Button>
          )}
        </div>
      </div>

      <section aria-labelledby="versions-title" className="grid gap-3">
        <h2 id="versions-title" className="text-lg font-semibold">
          {t.versionsTitle}
        </h2>
        {actionError && (
          <p role="alert" className={ALERT_CLASS}>
            {actionError}
          </p>
        )}
        {busy?.startsWith("preview") && (
          <p role="status" className="text-sm text-text-muted">
            {t.previewRunning}
          </p>
        )}
        {templates.isLoading ? (
          <div role="status" aria-label={fr.common.loading}>
            <Skeleton className="h-24 w-full" />
          </div>
        ) : versions.length === 0 ? (
          <p className="text-sm text-text-muted">{t.versionsEmpty}</p>
        ) : (
          <Table>
            <TableCaption className="sr-only">{t.versionsCaption}</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>{t.colVersion}</TableHead>
                <TableHead>{t.colStatus}</TableHead>
                <TableHead>{t.colFile}</TableHead>
                <TableHead>{t.colSize}</TableHead>
                <TableHead>{t.colDeposited}</TableHead>
                <TableHead>{t.colBy}</TableHead>
                <TableHead>{t.colComment}</TableHead>
                <TableHead>{t.colActions}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versions.map((g) => (
                <TableRow key={g.id} aria-label={`v${g.version}`}>
                  <TableCell>
                    <span className="inline-flex flex-wrap items-center gap-1">
                      {`v${g.version}`}
                      {g.provisoire && <Badge variant="secondary">{t.provisional}</Badge>}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={g.statut === "ACTIF" ? "default" : "outline"}>
                      {STATUT_GABARIT_LABELS[g.statut]}
                    </Badge>
                  </TableCell>
                  <TableCell>{g.nom_original}</TableCell>
                  <TableCell>{formatSize(g.taille)}</TableCell>
                  <TableCell>{formatDateTime(g.created_at)}</TableCell>
                  <TableCell>{g.created_by?.nom_complet ?? "—"}</TableCell>
                  <TableCell>{g.commentaire || "—"}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {isAdmin && g.statut !== "ACTIF" && (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={busy !== null}
                          onClick={(e) => {
                            opener.current = e.currentTarget;
                            setToActivate(g);
                          }}
                        >
                          {t.activate}
                        </Button>
                      )}
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={busy !== null}
                        onClick={() =>
                          void run(
                            `dl-${g.id}`,
                            (signal) => downloadTemplate(g.id, signal),
                            t.downloadError,
                          )
                        }
                      >
                        {t.download}
                      </Button>
                      {(["docx", "pdf"] as FormatFichier[]).map((format) => (
                        <Button
                          key={format}
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={busy !== null}
                          onClick={() =>
                            void run(
                              `preview-${g.id}-${format}`,
                              (signal) => previewTemplate(g.id, format, signal),
                              t.previewError,
                            )
                          }
                        >
                          {format === "docx" ? t.previewWord : t.previewPdf}
                        </Button>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <ContractFieldsPanel type={type} />

      {isAdmin && (
        <UploadTemplateDialog
          typeDocument={type.code}
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          onCloseAutoFocus={restoreAfterUpload}
        />
      )}
      {toActivate && (
        <ActivateTemplateDialog
          template={toActivate}
          onCloseAutoFocus={restoreFocus}
          open
          onOpenChange={(open) => {
            if (!open) setToActivate(null);
          }}
        />
      )}
    </div>
  );
}
