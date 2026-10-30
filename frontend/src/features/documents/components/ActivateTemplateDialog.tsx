import { useRef, useState } from "react";
import { isApiError } from "@/api/errors";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useActivateTemplate } from "../api";
import type { Gabarit } from "../types";

const t = fr.documentsAdmin;

type Props = {
  template: Gabarit;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCloseAutoFocus?: (event: Event) => void;
};

export function ActivateTemplateDialog({ template, open, onOpenChange, onCloseAutoFocus }: Props) {
  const activate = useActivateTemplate();
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);

  async function confirm() {
    if (busy.current) return;
    busy.current = true;
    setError(null);
    try {
      await activate.mutateAsync(template.id);
      onOpenChange(false);
    } catch (e) {
      setError(isApiError(e) ? e.detail : fr.errors.generic);
    } finally {
      busy.current = false;
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent onCloseAutoFocus={onCloseAutoFocus}>
        <AlertDialogHeader>
          <AlertDialogTitle>{t.activateTitle(template.version)}</AlertDialogTitle>
          <AlertDialogDescription>
            {t.activateText(template.type_document_libelle, template.version)}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error && (
          <p role="alert" className={ALERT_CLASS}>
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel type="button">{fr.common.cancel}</AlertDialogCancel>
          <Button type="button" disabled={activate.isPending} onClick={() => void confirm()}>
            {t.activateConfirm}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
