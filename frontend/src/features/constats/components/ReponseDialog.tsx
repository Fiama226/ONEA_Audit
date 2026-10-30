import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
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
import { useRespondFinding } from "../api";
import { reponseSchema, type ReponseFormValues } from "../schemas/constat";
import type { Constat, ReponseAudite } from "../types";

const t = fr.constatsUi;
const FIELDS = ["position", "commentaire", "confirme"] as const;

type Props = {
  constat: Constat;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Réponse de l'audité : le texte légal vient du serveur ; aucune confirmation n'est pré-cochée. */
export function ReponseDialog({ constat, open, onOpenChange }: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        {open && <ReponseForm constat={constat} onClose={() => onOpenChange(false)} />}
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ReponseForm({ constat, onClose }: { constat: Constat; onClose: () => void }) {
  const respond = useRespondFinding();
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState<ReponseAudite | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ReponseFormValues>({
    resolver: zodResolver(reponseSchema),
    defaultValues: { position: "", commentaire: "", confirme: false },
  });
  const position = useWatch({ control, name: "position" });

  async function submit(values: ReponseFormValues) {
    if (values.position === "") return;
    setFormError(null);
    try {
      const result = await respond.mutateAsync({
        missionId: constat.mission,
        data: {
          constat: constat.id,
          position: values.position,
          commentaire: values.commentaire.trim(),
          confirme: true,
          empreinte_soumise: constat.empreinte_soumise,
        },
      });
      setDone(result);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  if (done) {
    const [date = "", heure = ""] = formatDateTime(done.confirmation.confirme_le).split(" ");
    return (
      <>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {t.responseTitle.replace("{reference}", constat.reference)}
          </AlertDialogTitle>
          <AlertDialogDescription role="status">
            {t.responseDone
              .replace("{date}", date)
              .replace("{heure}", heure)
              .replace("{empreinte}", done.confirmation.empreinte)}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{fr.common.close}</AlertDialogCancel>
        </AlertDialogFooter>
      </>
    );
  }

  const text =
    position === "ACCORD"
      ? constat.texte_reponse?.accord
      : position === "DESACCORD"
        ? constat.texte_reponse?.desaccord
        : undefined;

  return (
    <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
      <AlertDialogHeader>
        <AlertDialogTitle>
          {t.responseTitle.replace("{reference}", constat.reference)}
        </AlertDialogTitle>
        <AlertDialogDescription>{constat.titre}</AlertDialogDescription>
      </AlertDialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <fieldset
        className="grid gap-2"
        aria-invalid={errors.position ? true : undefined}
        aria-describedby={errors.position ? "reponse-position-error" : undefined}
      >
        <legend className="text-sm font-medium">{t.responseChoice}</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" value="ACCORD" {...register("position")} />
          {t.responseAgree}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" value="DESACCORD" {...register("position")} />
          {t.responseDisagree}
        </label>
        {errors.position && (
          <p id="reponse-position-error" className="text-sm text-destructive">
            {errors.position.message}
          </p>
        )}
      </fieldset>
      {text && (
        <p className="rounded-md border border-border p-3 text-sm whitespace-pre-line">{text}</p>
      )}
      <FormField label={t.responseComment} error={errors.commentaire?.message}>
        {(p) => <Textarea {...p} rows={4} {...register("commentaire")} />}
      </FormField>
      <div className="grid gap-1">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            aria-invalid={errors.confirme ? true : undefined}
            aria-describedby={errors.confirme ? "reponse-confirme-error" : undefined}
            {...register("confirme")}
          />
          {t.responseConfirm}
        </label>
        {errors.confirme && (
          <p id="reponse-confirme-error" className="text-sm text-destructive">
            {errors.confirme.message}
          </p>
        )}
      </div>
      <AlertDialogFooter>
        <AlertDialogCancel type="button" onClick={onClose}>
          {fr.common.cancel}
        </AlertDialogCancel>
        <Button type="submit" disabled={respond.isPending}>
          {t.responseSubmit}
        </Button>
      </AlertDialogFooter>
    </form>
  );
}
