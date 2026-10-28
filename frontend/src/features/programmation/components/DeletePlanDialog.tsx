import { useNavigate } from "react-router-dom";
// Boîte de confirmation générique du référentiel, réutilisée telle quelle.
import { ConfirmDeleteDialog } from "@/features/referentiel/components/ConfirmDeleteDialog";
import { fr } from "@/i18n/fr";
import { useDeleteAuditPlan } from "../api";

/** Suppression d'un programme en brouillon, puis retour à la liste. */
export function DeletePlanDialog({
  id,
  open,
  onOpenChange,
}: {
  id: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const remove = useDeleteAuditPlan();
  return (
    <ConfirmDeleteDialog
      open={open}
      onOpenChange={onOpenChange}
      title={fr.programmationPlans.deleteTitle}
      description={fr.programmationPlans.deleteWarning}
      onConfirm={async () => {
        await remove.mutateAsync(id);
        void navigate("/programme-annuel");
      }}
      restoreFocus={() => undefined}
    />
  );
}
