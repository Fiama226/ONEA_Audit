import { flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";
import { fr } from "@/i18n/fr";
import { useDeleteAuditPlan, useForgetAuditPlan } from "../api";
import { ConfirmDeleteDialog } from "../shared";

/** Suppression d'un programme en brouillon, puis retour à la liste. */
export function DeletePlanDialog({
  id,
  open,
  onOpenChange,
  onDeleted,
}: {
  id: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Appelé dès la suppression acceptée : la page cesse d'observer le programme (sinon : 404). */
  onDeleted: () => void;
}) {
  const navigate = useNavigate();
  const remove = useDeleteAuditPlan();
  const forget = useForgetAuditPlan();
  return (
    <ConfirmDeleteDialog
      open={open}
      onOpenChange={onOpenChange}
      title={fr.programmationPlans.deleteTitle}
      description={fr.programmationPlans.deleteWarning}
      onConfirm={async () => {
        await remove.mutateAsync(id);
        // Rendu synchrone sans observateur, puis seulement retrait du cache et retour à la liste.
        flushSync(onDeleted);
        forget(id);
        void navigate("/programme-annuel");
      }}
      restoreFocus={() => undefined}
    />
  );
}
