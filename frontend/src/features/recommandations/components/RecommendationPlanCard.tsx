import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { PRIORITE_LABELS } from "@/features/constats/labels";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useDeleteAction, useWithdrawAcceptance } from "../api";
import { recommandationKeys } from "../keys";
import { STATUT_RECOMMANDATION_LABELS } from "../labels";
import type { AcceptationRisque, ActionCorrective, LigneRecommandation } from "../types";
import { ActionDialog } from "./ActionDialog";
import { ActionStatusBadge } from "./ActionStatusBadge";
import { EcheanceCell } from "./EcheanceCell";
import { RiskAcceptanceDialog } from "./RiskAcceptanceDialog";
import { ConfirmActionDialog } from "@/features/missions/components/ConfirmActionDialog";
import { StatusPill } from "@/components/StatusPill";
import { ScrollRegion } from "@/components/ui/scroll-region";

const t = fr.planActions;

type Props = {
  missionId: string;
  ligne: LigneRecommandation;
  /** Identifiant de la recommandation ; absent tant que la liste n'est pas chargée. */
  recommandationId: string | undefined;
  actions: ActionCorrective[];
  acceptation: AcceptationRisque | undefined;
  canAdd: boolean;
  canAccept: boolean;
  canWithdraw: boolean;
};

/** Recommandation d'un constat validé : statut dérivé, actions ou acceptation du risque. */
export function RecommendationPlanCard({
  missionId,
  ligne,
  recommandationId,
  actions,
  acceptation,
  canAdd,
  canAccept,
  canWithdraw,
}: Props) {
  const client = useQueryClient();
  const del = useDeleteAction();
  const withdraw = useWithdrawAcceptance();
  const [dialog, setDialog] = useState<"add" | "risk" | "withdraw" | null>(null);
  const [editing, setEditing] = useState<ActionCorrective | null>(null);
  const [deleting, setDeleting] = useState<ActionCorrective | null>(null);
  const headingId = `reco-${ligne.reference}`;
  const reco = recommandationId
    ? { id: recommandationId, reference: ligne.reference, libelle: ligne.libelle }
    : undefined;

  async function remove(action: ActionCorrective) {
    await del.mutateAsync({ id: action.id, missionId });
    // Les listes filtrées sur cette recommandation ne doivent plus montrer l'action supprimée.
    client.removeQueries({
      queryKey: [...recommandationKeys.all, "actions"],
      predicate: (q) =>
        (q.queryKey[2] as { recommandation?: string } | null)?.recommandation ===
        action.recommandation,
    });
  }

  return (
    <article
      aria-labelledby={headingId}
      className="grid gap-3 rounded-md border border-border p-4 break-inside-avoid"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="grid gap-1">
          <h4 id={headingId} className="text-sm font-semibold">
            {t.recommendation.replace("{reference}", ligne.reference)}
          </h4>
          <p className="text-sm">{ligne.libelle}</p>
          <p className="text-xs text-text-muted">
            {t.priority} : {PRIORITE_LABELS[ligne.priorite]}
          </p>
        </div>
        <StatusPill
          label={STATUT_RECOMMANDATION_LABELS[ligne.statut_derive]}
          tone={ligne.statut_derive === "REALISEE" ? "success" : "neutral"}
        />
      </header>

      {acceptation ? (
        <p className="rounded-md border border-border bg-surface-subtle p-3 text-sm">
          {t.accepted
            .replace("{date}", formatDate(acceptation.confirmation.confirme_le))
            .replace("{auteur}", acceptation.auteur.nom_complet)
            .replace("{motif}", acceptation.justification)}
        </p>
      ) : actions.length === 0 ? (
        <p className="text-sm text-text-muted">{t.noActions}</p>
      ) : (
        <ScrollRegion label={t.actionsCaption.replace("{reference}", ligne.reference)}>
          <table className="w-full text-left text-sm">
            <caption className="sr-only">
              {t.actionsCaption.replace("{reference}", ligne.reference)}
            </caption>
            <thead>
              <tr className="border-b border-border text-text-muted">
                {[t.colRef, t.colMeasure, t.colOwner, t.colDue, t.colIndicator, t.colMeans].map(
                  (h) => (
                    <th key={h} scope="col" className="py-2 pr-3">
                      {h}
                    </th>
                  ),
                )}
                <th scope="col" className="py-2 pr-3">
                  {t.colStatus}
                </th>
                <th scope="col" className="py-2 print:hidden">
                  <span className="sr-only">{t.colActions}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {actions.map((a) => (
                <tr key={a.id} className="border-b border-border align-top">
                  <td className="py-2 pr-3 font-medium">{a.reference}</td>
                  <td className="py-2 pr-3">{a.libelle}</td>
                  <td className="py-2 pr-3">{a.responsable_detail?.nom_complet ?? t.ownerNone}</td>
                  <td className="py-2 pr-3">
                    <EcheanceCell echeance={a.echeance} statut={a.statut} />
                  </td>
                  <td className="py-2 pr-3">{a.indicateur || t.none}</td>
                  <td className="py-2 pr-3">{a.moyens || t.none}</td>
                  <td className="py-2 pr-3">
                    <ActionStatusBadge statut={a.statut} />
                  </td>
                  <td className="py-2 print:hidden">
                    <div className="flex flex-wrap gap-2">
                      {a.actions_possibles.includes("MODIFIER") && (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          aria-label={`${t.editAction} ${a.reference}`}
                          onClick={() => setEditing(a)}
                        >
                          {t.editAction}
                        </Button>
                      )}
                      {a.actions_possibles.includes("SUPPRIMER") && (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          aria-label={`${t.deleteAction} ${a.reference}`}
                          onClick={() => setDeleting(a)}
                        >
                          {t.deleteAction}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}

      {reco && (canAdd || canAccept || canWithdraw) && (
        <div className="flex flex-wrap gap-2 print:hidden">
          {canAdd && (
            <Button type="button" variant="outline" onClick={() => setDialog("add")}>
              {t.addAction}
            </Button>
          )}
          {canAccept && (
            <Button type="button" variant="outline" onClick={() => setDialog("risk")}>
              {t.acceptRisk}
            </Button>
          )}
          {canWithdraw && acceptation && (
            <Button type="button" variant="outline" onClick={() => setDialog("withdraw")}>
              {t.withdrawAcceptance}
            </Button>
          )}
        </div>
      )}

      {reco && (
        <>
          <ActionDialog
            open={dialog === "add"}
            onOpenChange={(open) => !open && setDialog(null)}
            missionId={missionId}
            recommandation={reco}
          />
          <RiskAcceptanceDialog
            open={dialog === "risk"}
            onOpenChange={(open) => !open && setDialog(null)}
            missionId={missionId}
            recommandation={reco}
          />
          {editing && (
            <ActionDialog
              open
              onOpenChange={(open) => !open && setEditing(null)}
              missionId={missionId}
              recommandation={reco}
              action={editing}
            />
          )}
        </>
      )}
      {acceptation && (
        <ConfirmActionDialog
          open={dialog === "withdraw"}
          onOpenChange={(open) => !open && setDialog(null)}
          title={t.withdrawTitle}
          text={t.withdrawText}
          confirmLabel={t.withdrawAcceptance}
          requireCheck={false}
          onConfirm={() => withdraw.mutateAsync({ id: acceptation.id, missionId })}
        />
      )}
      {deleting && (
        <ConfirmActionDialog
          open
          onOpenChange={(open) => !open && setDeleting(null)}
          title={t.deleteTitle.replace("{reference}", deleting.reference)}
          text={t.deleteText}
          confirmLabel={t.deleteAction}
          onConfirm={() => remove(deleting)}
        />
      )}
    </article>
  );
}
