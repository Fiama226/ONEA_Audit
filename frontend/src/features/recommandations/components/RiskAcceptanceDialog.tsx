import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
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
import { fr } from "@/i18n/fr";
import { formatDateTime } from "@/lib/dates";
import { useAcceptRisk } from "../api";
import { RISK_FIELDS, riskAcceptanceSchema, type RiskAcceptanceValues } from "../schemas/action";
import type { AcceptationRisque } from "../types";

const t = fr.planActions;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  missionId: string;
  recommandation: { id: string; reference: string; libelle: string };
};

/**
 * Acceptation du risque d'une recommandation sans action. La case de confirmation n'est jamais
 * pré-cochée ; le texte exact confirmé est celui du serveur, affiché une fois l'acceptation enregistrée.
 */
export function RiskAcceptanceDialog({ open, onOpenChange, ...rest }: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        {open && <RiskForm {...rest} onClose={() => onOpenChange(false)} />}
      </AlertDialogContent>
    </AlertDialog>
  );
}

function RiskForm({
  missionId,
  recommandation,
  onClose,
}: Omit<Props, "open" | "onOpenChange"> & { onClose: () => void }) {
  const accept = useAcceptRisk();
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState<AcceptationRisque | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RiskAcceptanceValues>({
    resolver: zodResolver(riskAcceptanceSchema),
    defaultValues: { justification: "", confirme: false },
  });
  const title = t.riskTitle.replace("{reference}", recommandation.reference);

  async function submit(values: RiskAcceptanceValues) {
    setFormError(null);
    try {
      setDone(
        await accept.mutateAsync({
          missionId,
          data: {
            recommandation: recommandation.id,
            justification: values.justification.trim(),
            confirme: true,
          },
        }),
      );
    } catch (e) {
      setFormError(applyApiErrors(e, setError, RISK_FIELDS));
    }
  }

  if (done) {
    const [date = "", heure = ""] = formatDateTime(done.confirmation.confirme_le).split(" ");
    return (
      <>
        <AlertDialogHeader>
          <AlertDialogTitle>{t.riskDoneTitle}</AlertDialogTitle>
          <AlertDialogDescription role="status">
            {t.riskDone
              .replace("{date}", date)
              .replace("{heure}", heure)
              .replace("{empreinte}", done.confirmation.empreinte)}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <p className="text-sm font-medium">{t.riskRecordedText}</p>
        <p className="rounded-md border border-border p-3 text-sm whitespace-pre-line">
          {done.texte}
        </p>
        <AlertDialogFooter>
          <AlertDialogCancel>{fr.common.close}</AlertDialogCancel>
        </AlertDialogFooter>
      </>
    );
  }

  return (
    <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
      <AlertDialogHeader>
        <AlertDialogTitle>{title}</AlertDialogTitle>
        <AlertDialogDescription>
          {t.riskIntro.replace("{libelle}", recommandation.libelle)}
        </AlertDialogDescription>
      </AlertDialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.riskJustification} error={errors.justification?.message}>
        {(p) => <Textarea {...p} rows={4} {...register("justification")} />}
      </FormField>
      <div className="grid gap-1">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            aria-invalid={errors.confirme ? true : undefined}
            aria-describedby={errors.confirme ? "risk-confirme-error" : undefined}
            {...register("confirme")}
          />
          {t.riskConfirm}
        </label>
        {errors.confirme && (
          <p id="risk-confirme-error" className="text-sm text-destructive">
            {errors.confirme.message}
          </p>
        )}
      </div>
      <AlertDialogFooter>
        <AlertDialogCancel type="button" onClick={onClose}>
          {fr.common.cancel}
        </AlertDialogCancel>
        <Button type="submit" disabled={accept.isPending}>
          {t.riskSubmit}
        </Button>
      </AlertDialogFooter>
    </form>
  );
}
