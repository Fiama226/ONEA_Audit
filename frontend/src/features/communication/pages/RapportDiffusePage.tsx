import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import { PrintLayout } from "@/components/print/PrintLayout";
import { Button } from "@/components/ui/button";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { downloadReport, useReport, useReportAction } from "../api";
import { AppreciationBadge } from "../components/AppreciationBadge";
import type { DocumentRapport, FormatRapport, Rapport, RapportDiffuse } from "../types";

const t = fr.rapportFinal;

const DOWNLOADS: { document: DocumentRapport; format: FormatRapport; label: string }[] = [
  { document: "rapport", format: "docx", label: t.downloadReportWord },
  { document: "rapport", format: "pdf", label: t.downloadReportPdf },
  { document: "note", format: "docx", label: t.downloadNoteWord },
  { document: "note", format: "pdf", label: t.downloadNotePdf },
];

/** Lecture d'un rapport diffusé (DG, audité, destinataire) : synthèse, téléchargements, accusé. */
export function RapportDiffusePage() {
  const { id } = useParams();
  const report = useReport(id);

  if (report.isPending) return <p role="status">{fr.common.loading}</p>;
  if (report.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.detailLoadError}
      </p>
    );
  }
  return <Detail data={report.data} />;
}

function isDiffuse(data: Rapport | RapportDiffuse): data is RapportDiffuse {
  return "mission_reference" in data;
}

function Detail({ data }: { data: Rapport | RapportDiffuse }) {
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const action = useReportAction();
  const diffuse = isDiffuse(data);
  const title = diffuse
    ? `${data.mission_reference} · ${data.mission_titre}`
    : fr.communication.distributedDetailTitle;
  const mention = diffuse ? data.mention_correction : data.motif_correction;
  const ack = diffuse ? data.mon_accuse_reception : null;
  const canAck = data.actions_possibles.includes("ACCUSER_RECEPTION") && !ack;

  async function download(document: DocumentRapport, format: FormatRapport) {
    setDownloadError(null);
    try {
      await downloadReport(data.id, format, document);
    } catch (e) {
      setDownloadError(e instanceof Error && e.message ? e.message : fr.documents.downloadError);
    }
  }

  return (
    <section aria-labelledby="rapport-diffuse-title" className="grid gap-4">
      <div className="print:hidden">
        <Link className="text-sm underline" to="/rapports">
          {t.detailBack}
        </Link>
      </div>
      <PrintLayout
        title={fr.communication.distributedDetailTitle}
        reference={diffuse ? data.numero_document : undefined}
      >
        <div className="grid gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <h1 id="rapport-diffuse-title" className="text-2xl font-semibold tracking-[-0.012em]">
              {title}
            </h1>
            <AppreciationBadge appreciation={data.appreciation_globale} />
          </div>
          {mention !== "" && (
            <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm">{mention}</p>
          )}
          <p className="text-sm text-text-muted">
            {t.versionLabel.replace("{n}", String(data.numero_version))}
            {diffuse && data.diffuse_le
              ? ` · ${t.colDistributed} ${formatDate(data.diffuse_le)}`
              : ""}
          </p>
          <section aria-labelledby="diffuse-summary-title" className="grid gap-1">
            <h3 id="diffuse-summary-title" className="text-base font-semibold">
              {t.detailSummary}
            </h3>
            <p className="text-sm whitespace-pre-line">{data.synthese}</p>
          </section>
          <p className="text-sm">
            <span className="text-text-muted">{t.detailAppreciation} : </span>
            <AppreciationBadge appreciation={data.appreciation_globale} />
          </p>
        </div>
      </PrintLayout>
      <section aria-labelledby="diffuse-downloads-title" className="grid gap-2 print:hidden">
        <h3 id="diffuse-downloads-title" className="text-base font-semibold">
          {t.detailDownloads}
        </h3>
        {downloadError && (
          <p role="alert" className={ALERT_CLASS}>
            {downloadError}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {DOWNLOADS.map((d) => (
            <Button
              key={`${d.document}-${d.format}`}
              type="button"
              variant="outline"
              onClick={() => void download(d.document, d.format)}
            >
              {d.label}
            </Button>
          ))}
        </div>
      </section>
      <div className="print:hidden">
        {ack && (
          <p role="status" className="text-sm">
            {t.acknowledged.replace("{date}", formatDate(ack))}
          </p>
        )}
        {canAck && (
          <>
            <Button type="button" onClick={() => setAcknowledging(true)}>
              {t.acknowledge}
            </Button>
            <ConfirmActionDialog
              open={acknowledging}
              onOpenChange={setAcknowledging}
              title={t.acknowledgeTitle}
              text={t.acknowledgeText}
              confirmLabel={t.acknowledgeConfirm}
              onConfirm={() =>
                action.mutateAsync({
                  id: data.id,
                  missionId: "mission" in data ? data.mission : "",
                  action: "acknowledge",
                })
              }
            />
          </>
        )}
      </div>
    </section>
  );
}
