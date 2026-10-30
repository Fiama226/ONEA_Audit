import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ALERT_CLASS } from "@/components/form/FormField";
import { UserPicker } from "@/features/missions/components/UserPicker";
import { fr } from "@/i18n/fr";
import { useChangeResponsible } from "../api";
import { fieldErrorsOf, generalErrorOf } from "../serverErrors";
import type { ActionSuivie } from "../types";

const t = fr.suiviRegistre;

type Props = {
  action: ActionSuivie;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Changement de responsable (RAI) : choix unique parmi les utilisateurs audités actifs. */
export function ResponsibleDialog({ action, open, onOpenChange }: Props) {
  const change = useChangeResponsible();
  const [value, setValue] = useState<string[]>([]);
  const [fieldError, setFieldError] = useState<string>();
  const [general, setGeneral] = useState<string>();

  function close(next: boolean) {
    if (change.isPending) return;
    if (!next) {
      setValue([]);
      setFieldError(undefined);
      setGeneral(undefined);
    }
    onOpenChange(next);
  }

  async function save() {
    setGeneral(undefined);
    if (value.length === 0) {
      setFieldError(t.responsibleRequired);
      return;
    }
    setFieldError(undefined);
    try {
      await change.mutateAsync({ id: action.id, responsable: Number(value[0]) });
      close(false);
    } catch (e) {
      setFieldError(fieldErrorsOf(e).responsable);
      setGeneral(generalErrorOf(e));
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.responsibleTitle}</DialogTitle>
          <DialogDescription>{t.responsibleDescription}</DialogDescription>
        </DialogHeader>
        <UserPicker
          single
          // eslint-disable-next-line jsx-a11y/aria-role -- `role` est ici le rôle métier, pas un rôle ARIA
          role="AUDITE"
          label={t.responsiblePicker}
          value={value}
          onChange={setValue}
          exclude={[String(action.responsable.id)]}
          error={fieldError}
        />
        {general && (
          <p role="alert" className={ALERT_CLASS}>
            {general}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => close(false)}>
            {fr.common.cancel}
          </Button>
          <Button type="button" disabled={change.isPending} onClick={() => void save()}>
            {t.responsibleSave}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
