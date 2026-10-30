import { useState } from "react";
import { ALERT_CLASS } from "@/components/form/FormField";
import { StatusPill, type PillTone } from "@/components/StatusPill";
import { Button } from "@/components/ui/button";
import { ConfirmationTextDialog } from "@/features/communication/components/ConfirmationTextDialog";
import { fr } from "@/i18n/fr";
import { useCommit, useCommitmentText } from "../api";
import type { EtatEngagement, SynthesePlan } from "../types";
import { EcheanceCell } from "./EcheanceCell";

const t = fr.planActions;

const ETAT: Record<EtatEngagement, { label: string; tone: PillTone }> = {
  CONFIRME: { label: t.commitmentConfirmed, tone: "success" },
  A_RENOUVELER: { label: t.commitmentRenew, tone: "warning" },
  NON_CONFIRME: { label: t.commitmentMissing, tone: "neutral" },
};

export function EtatEngagementPill({ etat }: { etat: EtatEngagement }) {
  return <StatusPill label={ETAT[etat].label} tone={ETAT[etat].tone} />;
}

type Props = {
  missionId: string;
  summary: SynthesePlan;
  /** Vue de l'audité (confirmation de son engagement) ou de l'équipe (état par responsable). */
  audite: boolean;
  /** Plan modifiable : l'engagement ne se confirme que pendant la fenêtre de saisie. */
  writable: boolean;
};

/** Engagement des responsables sur leur plan d'actions. */
export function CommitmentPanel({ missionId, summary, audite, writable }: Props) {
  return (
    <section
      aria-labelledby="commitment-title"
      className="grid gap-3 rounded-md border border-border p-4 break-inside-avoid"
    >
      <h4 id="commitment-title" className="text-sm font-semibold">
        {t.commitmentTitle}
      </h4>
      {audite ? (
        <AuditeeCommitment missionId={missionId} writable={writable} />
      ) : summary.responsables.length === 0 ? (
        <p className="text-sm text-text-muted">{t.commitmentNoOwners}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{t.commitmentTable}</caption>
            <thead>
              <tr className="border-b border-border text-text-muted">
                <th scope="col" className="py-2 pr-3">
                  {t.colOwner}
                </th>
                <th scope="col" className="py-2 pr-3">
                  {t.colActionsCount}
                </th>
                <th scope="col" className="py-2 pr-3">
                  {t.colNextDue}
                </th>
                <th scope="col" className="py-2">
                  {t.colCommitment}
                </th>
              </tr>
            </thead>
            <tbody>
              {summary.responsables.map((r) => (
                <tr key={r.utilisateur.id} className="border-b border-border">
                  <td className="py-2 pr-3">{r.utilisateur.nom_complet}</td>
                  <td className="py-2 pr-3">{r.nb_actions}</td>
                  <td className="py-2 pr-3">
                    <EcheanceCell echeance={r.prochaine_echeance} statut="A_LANCER" />
                  </td>
                  <td className="py-2">
                    <EtatEngagementPill etat={r.engagement} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AuditeeCommitment({ missionId, writable }: { missionId: string; writable: boolean }) {
  const text = useCommitmentText(missionId);
  const commit = useCommit();
  const [open, setOpen] = useState(false);

  if (text.isError) {
    return (
      <p role="alert" className={ALERT_CLASS}>
        {t.commitmentLoadError}
      </p>
    );
  }
  if (!text.data) {
    return (
      <p role="status" className="text-sm text-text-muted">
        {fr.common.loading}
      </p>
    );
  }
  const { etat, nb_actions, texte } = text.data;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <EtatEngagementPill etat={etat} />
        {nb_actions === 0 && <p className="text-sm text-text-muted">{t.commitmentNoActions}</p>}
      </div>
      {etat === "A_RENOUVELER" && <p className="text-sm">{t.commitmentRenewHelp}</p>}
      {writable && nb_actions > 0 && etat !== "CONFIRME" && (
        <div className="print:hidden">
          <Button type="button" onClick={() => setOpen(true)}>
            {t.commitmentConfirm}
          </Button>
        </div>
      )}
      <ConfirmationTextDialog
        open={open}
        onOpenChange={setOpen}
        title={t.commitmentDialogTitle}
        texte={texte}
        confirmLabel={t.commitmentConfirm}
        onConfirm={async () => {
          const result = await commit.mutateAsync({ missionId });
          return result.confirmation;
        }}
      />
    </div>
  );
}
