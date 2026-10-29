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
import { MOTIF_NON_TEST_LABELS } from "../labels";
import { nonTestSchema, type NonTestFormValues } from "../schemas/objective";
import type { MotifNonTest, ObjectifAudit } from "../types";

const t = fr.analyseVII;

type Props = {
  objective: ObjectifAudit | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (objective: ObjectifAudit, values: NonTestFormValues) => Promise<unknown>;
};

export function NonTestDialog({ objective, onOpenChange, onSubmit }: Props) {
  return (
    <Dialog open={objective !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        {objective && (
          <NonTestForm
            objective={objective}
            onSubmit={onSubmit}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function NonTestForm({
  objective,
  onSubmit,
  onDone,
}: {
  objective: ObjectifAudit;
  onSubmit: Props["onSubmit"];
  onDone: () => void;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<NonTestFormValues>({
    resolver: zodResolver(nonTestSchema),
    defaultValues: { motif_non_test: "", justification: "" },
  });

  async function submit(values: NonTestFormValues) {
    setFormError(null);
    try {
      await onSubmit(objective, values);
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["motif_non_test", "justification"]));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t.nonTestTitle}</DialogTitle>
        <DialogDescription>
          {t.nonTestDescription}
          {objective.code}.
        </DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <Controller
        control={control}
        name="motif_non_test"
        render={({ field }) => (
          <FormField label={t.reasonLabel} error={errors.motif_non_test?.message}>
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
                <option value="">{t.reasonPlaceholder}</option>
                {(Object.keys(MOTIF_NON_TEST_LABELS) as MotifNonTest[]).map((k) => (
                  <option key={k} value={k}>
                    {MOTIF_NON_TEST_LABELS[k]}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        )}
      />
      <FormField label={t.justificationLabel} error={errors.justification?.message}>
        {(p) => <Textarea {...p} rows={4} required {...register("justification")} />}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {t.confirmNonTest}
        </Button>
      </DialogFooter>
    </form>
  );
}
