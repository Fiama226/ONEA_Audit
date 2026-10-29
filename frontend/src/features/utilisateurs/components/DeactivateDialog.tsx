import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
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
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ALERT_CLASS, FormField } from "@/features/referentiel/components/FormField";
import { fr } from "@/i18n/fr";
import { useAccountAction } from "../api";
import { deactivateSchema, type DeactivateFormValues } from "../schemas";
import type { CompteUtilisateur } from "../types";

const t = fr.utilisateurs.fiche;

type Props = {
  account: CompteUtilisateur;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
  onCloseAutoFocus?: (event: Event) => void;
};

export function DeactivateDialog({ account, open, onOpenChange, onDone, onCloseAutoFocus }: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent onCloseAutoFocus={onCloseAutoFocus}>
        <DeactivateForm account={account} onCancel={() => onOpenChange(false)} onDone={onDone} />
      </AlertDialogContent>
    </AlertDialog>
  );
}

function DeactivateForm({
  account,
  onCancel,
  onDone,
}: Pick<Props, "account" | "onDone"> & { onCancel: () => void }) {
  const action = useAccountAction();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError: setFieldError,
    formState: { errors },
  } = useForm<DeactivateFormValues>({
    resolver: zodResolver(deactivateSchema),
    defaultValues: { motif: "" },
  });

  async function onSubmit(values: DeactivateFormValues) {
    setError(null);
    try {
      await action.mutateAsync({ id: account.id, action: "deactivate", motif: values.motif });
      onDone();
    } catch (e) {
      if (!isApiError(e)) return setError(fr.errors.generic);
      const motif = e.errors.motif;
      if (motif && motif.length > 0) {
        setFieldError("motif", { type: "server", message: motif.join(" ") }, { shouldFocus: true });
      } else {
        setError(e.detail);
      }
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <AlertDialogHeader>
        <AlertDialogTitle>{`${t.deactivateTitle}${account.nom_complet} ?`}</AlertDialogTitle>
        <AlertDialogDescription>{t.deactivateText}</AlertDialogDescription>
      </AlertDialogHeader>
      {error && (
        <p role="alert" className={ALERT_CLASS}>
          {error}
        </p>
      )}
      <FormField label={t.reason} error={errors.motif?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("motif")} />}
      </FormField>
      <AlertDialogFooter>
        <AlertDialogCancel type="button" disabled={action.isPending} onClick={onCancel}>
          {fr.common.cancel}
        </AlertDialogCancel>
        <Button type="submit" variant="destructive" disabled={action.isPending}>
          {t.deactivateConfirm}
        </Button>
      </AlertDialogFooter>
    </form>
  );
}
