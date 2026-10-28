import { useState } from "react";
import { isApiError } from "@/api/errors";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { fr } from "@/i18n/fr";
import { useValidateAuditPlan } from "../api";

/** Confirmation d'une action irréversible ; un refus du serveur (422) reste affiché dans la boîte. */
export function ValidatePlanDialog({
  id,
  open,
  onOpenChange,
}: {
  id: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const validate = useValidateAuditPlan();
  const [error, setError] = useState<string | null>(null);
  const c = fr.programmationPlans;

  function handleOpenChange(next: boolean) {
    if (!next) setError(null);
    onOpenChange(next);
  }

  async function confirm() {
    setError(null);
    try {
      await validate.mutateAsync(id);
      handleOpenChange(false);
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{c.validateTitle}</AlertDialogTitle>
          <AlertDialogDescription>{c.validateWarning}</AlertDialogDescription>
        </AlertDialogHeader>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>{fr.common.cancel}</AlertDialogCancel>
          <AlertDialogAction
            disabled={validate.isPending}
            onClick={(e) => {
              e.preventDefault();
              void confirm();
            }}
          >
            {validate.isPending ? c.validating : c.validateConfirm}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
