import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useGiveOpinion } from "../api";
import { TYPE_AVIS_LABELS } from "../labels";
import { opinionSchema, type OpinionFormValues } from "../schemas/opinion";
import type { TypeAvis } from "../types";

const t = fr.analyseVVI;

type Props = { open: boolean; onOpenChange: (open: boolean) => void; missionId: string };

export function OpinionDialog({ open, onOpenChange, missionId }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <OpinionForm missionId={missionId} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function OpinionForm({ missionId, onDone }: { missionId: string; onDone: () => void }) {
  const give = useGiveOpinion();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<OpinionFormValues>({
    resolver: zodResolver(opinionSchema),
    defaultValues: { avis: "", commentaire: "" },
  });

  async function onSubmit(values: OpinionFormValues) {
    setFormError(null);
    if (values.avis === "") return;
    try {
      await give.mutateAsync({ missionId, avis: values.avis, commentaire: values.commentaire });
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["avis", "commentaire"]));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t.opinionTitle}</DialogTitle>
        <DialogDescription>{t.opinionDesc}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <Controller
        control={control}
        name="avis"
        render={({ field }) => (
          <FormField label={t.opinionType} error={errors.avis?.message}>
            {(p) => (
              <NativeSelect
                {...p}
                required
                name={field.name}
                ref={field.ref}
                value={field.value}
                onBlur={field.onBlur}
                onChange={(e) => field.onChange(e.target.value)}
              >
                <option value="">{t.choose}</option>
                {(Object.keys(TYPE_AVIS_LABELS) as TypeAvis[]).map((k) => (
                  <option key={k} value={k}>
                    {TYPE_AVIS_LABELS[k]}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        )}
      />
      <FormField label={t.opinionComment} error={errors.commentaire?.message}>
        {(p) => <Textarea {...p} rows={4} {...register("commentaire")} />}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={give.isPending}>
          {fr.common.confirm}
        </Button>
      </DialogFooter>
    </form>
  );
}
