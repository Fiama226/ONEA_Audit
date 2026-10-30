import { useState } from "react";
import { useParams } from "react-router-dom";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { PrintLayout } from "@/components/print/PrintLayout";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useCreateReport, useMissionReport } from "../api";
import { RapportStatusBadge } from "../components/RapportStatusBadge";
import { ReportActions } from "../components/ReportActions";
import { ReportJournal } from "../components/ReportJournal";
import { ReportPreview } from "../components/ReportPreview";
import { ReportSectionsForm } from "../components/ReportSectionsForm";

const t = fr.rapportFinal;

/** Rapport d'audit de la mission : rédaction, aperçu, soumission et validation. */
export function RapportPage() {
  const { id } = useParams();
  const report = useMissionReport(id);
  const create = useCreateReport();
  const [createError, setCreateError] = useState<string | null>(null);

  async function createReport() {
    setCreateError(null);
    try {
      await create.mutateAsync({ missionId: id ?? "" });
    } catch (e) {
      setCreateError(isApiError(e) ? e.detail : t.createError);
    }
  }

  let body;
  if (report.isPending) {
    body = <p role="status">{fr.common.loading}</p>;
  } else if (report.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else if (report.data === null) {
    body = (
      <div className="grid gap-3">
        <p className="text-sm text-text-muted">{t.noReport}</p>
        {createError && (
          <p role="alert" className={ALERT_CLASS}>
            {createError}
          </p>
        )}
        <div>
          <Button type="button" disabled={create.isPending} onClick={() => void createReport()}>
            {t.createReport}
          </Button>
        </div>
      </div>
    );
  } else {
    const rapport = report.data;
    body = (
      <div className="grid gap-6">
        <div className="flex flex-wrap items-center gap-3 text-sm print:hidden">
          <RapportStatusBadge statut={rapport.statut} />
          <span>{t.versionLabel.replace("{n}", String(rapport.numero_version))}</span>
        </div>
        {rapport.statut === "RENVOYE" && rapport.motif_renvoi !== "" && (
          <div role="alert" className={`${ALERT_CLASS} print:hidden`}>
            <p className="font-semibold">{t.returnedTitle}</p>
            <p className="whitespace-pre-line">{rapport.motif_renvoi}</p>
          </div>
        )}
        <ReportActions rapport={rapport} />
        <div className="print:hidden">
          <ReportSectionsForm
            key={`${rapport.id}-${rapport.statut}-${rapport.cycle}`}
            rapport={rapport}
            readOnly={!rapport.actions_possibles.includes("MODIFIER")}
          />
        </div>
        <div className="print:hidden">
          <ReportJournal evenements={rapport.evenements} />
        </div>
        <section aria-labelledby="report-preview-title" className="grid gap-3">
          <div className="flex items-center justify-between gap-3 print:hidden">
            <h3 id="report-preview-title" className="text-base font-semibold">
              {t.previewTitle}
            </h3>
            <Button type="button" variant="outline" onClick={() => window.print()}>
              {t.print}
            </Button>
          </div>
          <PrintLayout title={fr.communication.reportPageTitle}>
            <ReportPreview rapportId={rapport.id} />
          </PrintLayout>
        </section>
      </div>
    );
  }

  return (
    <section aria-labelledby="rapport-title" className="grid gap-4">
      <h2 id="rapport-title" className="text-lg font-semibold print:hidden">
        {fr.communication.reportPageTitle}
      </h2>
      {body}
    </section>
  );
}
