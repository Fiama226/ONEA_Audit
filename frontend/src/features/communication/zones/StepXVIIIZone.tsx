import { useState } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import type { ZoneProps } from "@/features/missions/zones";
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useMissionReport, useRecipients, useReportAction, useReportSignature } from "../api";
import { CorrectedReportDialog } from "../components/CorrectedReportDialog";
import { DistributionTracking } from "../components/DistributionTracking";
import { DocumentSlot } from "../components/DocumentSlot";
import { RapportStatusBadge } from "../components/RapportStatusBadge";
import { RecipientsEditor } from "../components/RecipientsEditor";
import { SignaturePanel } from "../components/SignaturePanel";
import { ValidationPanel } from "../components/ValidationPanel";
import type { Rapport } from "../types";

const t = fr.rapportFinal;

/** Raison pour laquelle « Diffuser » est indisponible, ou null si la diffusion est possible. */
export function distributeBlocker(
  rapport: Rapport,
  recipientCount: number | undefined,
  signed = false,
): string | null {
  const final = rapport.version_finale;
  if (!final || final.statut !== "PRETE") return t.notGenerated;
  if (final.statut_pdf !== "PRET") return t.pdfNotReady;
  if (rapport.signature_electronique_requise && !signed) return t.signatureMissing;
  if (recipientCount === 0) return t.noRecipients;
  return null;
}

/** Étape XVIII : validation par le RAI, génération, diffusion et suivi du rapport. */
export function StepXVIIIZone({ mission, step }: ZoneProps) {
  const report = useMissionReport(mission.id);
  const titleId = `zone-XVIII-${step.id}`;
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
  } else if (report.data === null) {
    body = <p className="text-sm text-text-muted">{t.noReport}</p>;
  } else {
    body = <ReportFlow rapport={report.data} />;
  }
  return (
    <section aria-labelledby={titleId} className="grid gap-4 rounded-md border border-border p-4">
      <h3 id={titleId} className="text-base font-semibold">
        {fr.communication.zoneXVIIITitle}
      </h3>
      {body}
    </section>
  );
}

function ReportFlow({ rapport }: { rapport: Rapport }) {
  const validated = rapport.statut === "VALIDE" || rapport.statut === "DIFFUSE";
  const confirmation = rapport.confirmation_validation;
  const [date = "", heure = ""] = confirmation
    ? formatDateTime(confirmation.confirme_le).split(" ")
    : [];

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <RapportStatusBadge statut={rapport.statut} />
        <span>{t.versionLabel.replace("{n}", String(rapport.numero_version))}</span>
      </div>
      {rapport.statut === "SOUMIS" &&
        (rapport.actions_possibles.includes("VALIDER") ||
        rapport.actions_possibles.includes("RENVOYER") ? (
          <ValidationPanel rapport={rapport} />
        ) : (
          <p role="status" className="text-sm text-text-muted">
            {t.awaitingRai}
          </p>
        ))}
      {validated && (
        <>
          {confirmation && (
            <p className="text-sm">
              {t.validatedOn
                .replace("{date}", date)
                .replace("{heure}", heure)
                .replace("{empreinte}", confirmation.empreinte)}
            </p>
          )}
          {rapport.mode_signature !== "" && (
            <p className="text-sm">
              <span className="text-text-muted">{t.signatureMode} : </span>
              <span className="font-medium">{t.modes[rapport.mode_signature]}</span>
            </p>
          )}
          <section aria-labelledby="generation-title" className="grid gap-2">
            <h3 id="generation-title" className="text-base font-semibold">
              {t.generationTitle}
            </h3>
            {!rapport.version_finale && (
              <p role="status" className="text-sm text-text-muted">
                {t.generationPending}
              </p>
            )}
            <DocumentSlot
              typeDocument="RAPPORT_FINAL"
              objetId={rapport.id}
              missionId={rapport.mission}
            />
            <DocumentSlot
              typeDocument="NOTE_SYNTHETIQUE"
              objetId={rapport.id}
              missionId={rapport.mission}
            />
          </section>
          <SignaturePanel rapport={rapport} />
          <RecipientsEditor
            rapportId={rapport.id}
            missionId={rapport.mission}
            readOnly={rapport.statut === "DIFFUSE"}
          />
        </>
      )}
      {rapport.statut === "VALIDE" && <DistributeControl rapport={rapport} />}
      {rapport.statut === "DIFFUSE" && (
        <>
          {rapport.diffusion && (
            <p className="text-sm">
              {t.distributedOn
                .replace("{date}", formatDateTime(rapport.diffusion.diffusee_le))
                .replace("{nom}", rapport.diffusion.diffusee_par.nom_complet)}
            </p>
          )}
          <DistributionTracking
            rapportId={rapport.id}
            missionId={rapport.mission}
            canMark={
              rapport.actions_possibles.includes("DIFFUSER") ||
              rapport.actions_possibles.includes("CORRIGER")
            }
          />
          {rapport.actions_possibles.includes("CORRIGER") && (
            <CorrectedReportDialog rapport={rapport} />
          )}
        </>
      )}
    </div>
  );
}

function DistributeControl({ rapport }: { rapport: Rapport }) {
  const recipients = useRecipients(rapport.id);
  const signature = useReportSignature(rapport.id, rapport.signature_electronique_requise);
  const action = useReportAction();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  if (!rapport.actions_possibles.includes("DIFFUSER")) return null;
  const reason = distributeBlocker(
    rapport,
    recipients.data?.results.length,
    signature.data?.signee === true,
  );
  const reasonId = "distribute-reason";

  return (
    <div className="grid gap-2">
      <label className="grid gap-1.5 text-sm font-medium" htmlFor="distribute-message">
        {t.distributeMessage}
        <Textarea
          id="distribute-message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={2}
        />
      </label>
      <div>
        <Button
          type="button"
          disabled={reason !== null}
          aria-describedby={reason ? reasonId : undefined}
          onClick={() => setOpen(true)}
        >
          {t.distribute}
        </Button>
      </div>
      {reason && (
        <p id={reasonId} className="text-sm text-text-muted">
          {reason}
        </p>
      )}
      <ConfirmActionDialog
        open={open}
        onOpenChange={setOpen}
        title={t.distributeTitle}
        text={t.distributeText}
        confirmLabel={t.distributeConfirm}
        onConfirm={() =>
          action.mutateAsync({
            id: rapport.id,
            missionId: rapport.mission,
            action: "distribute",
            payload: { message },
          })
        }
      />
    </div>
  );
}
