import { useState } from "react";
import { isApiError } from "@/api/errors";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fr } from "@/i18n/fr";
import { useValidateRiskMap } from "../api";

export function ValidateRiskMapDialog({
  id,
  open,
  onOpenChange,
}: {
  id: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const validate = useValidateRiskMap();
  const [error, setError] = useState<string | null>(null);
  const c = fr.refCartographie;

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
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{c.validateTitle}</DialogTitle>
          <DialogDescription>{c.validateWarning}</DialogDescription>
        </DialogHeader>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            {fr.common.cancel}
          </Button>
          <Button type="button" disabled={validate.isPending} onClick={() => void confirm()}>
            {validate.isPending ? c.validating : c.validateConfirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
