import { Link } from "react-router-dom";
import { ALERT_CLASS } from "@/components/form/FormField";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { useMissionReport } from "../api";
import { RapportStatusBadge } from "../components/RapportStatusBadge";

const t = fr.rapportFinal;

/** Étape XVII : rédaction du rapport ; le travail se fait sur la page du rapport. */
export function StepXVIIZone({ mission, step }: ZoneProps) {
  const report = useMissionReport(mission.id);
  const titleId = `zone-XVII-${step.id}`;
  let body;
  if (report.isPending) {
    body = (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  } else if (report.isError) {
    body = (
      <p role="alert" className={ALERT_CLASS}>
        {t.loadError}
      </p>
    );
  } else {
    body = (
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {report.data ? (
          <>
            <RapportStatusBadge statut={report.data.statut} />
            <span>{t.versionLabel.replace("{n}", String(report.data.numero_version))}</span>
          </>
        ) : (
          <span className="text-text-muted">{t.noReport}</span>
        )}
        <Link className="font-medium underline" to={`/missions/${mission.id}/rapport`}>
          {t.openReport}
        </Link>
      </div>
    );
  }
  return (
    <section aria-labelledby={titleId} className="grid gap-2 rounded-md border border-border p-4">
      <h3 id={titleId} className="text-base font-semibold">
        {fr.communication.zoneXVIITitle}
      </h3>
      {body}
    </section>
  );
}
