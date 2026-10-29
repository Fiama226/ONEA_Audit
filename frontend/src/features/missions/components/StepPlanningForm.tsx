import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { useUpdateStepPlanning } from "../api";
import {
  stepPlanningSchema,
  toPlanningPayload,
  type StepPlanningValues,
} from "../schemas/stepPlanning";
import type { Etape } from "../types";

const m = fr.missionEtapes;
const FIELDS = [
  "date_debut_prevue",
  "date_fin_prevue",
  "charge_prevue_jours",
  "charge_reelle_jours",
] as const;

/** Décimal serveur « 2.50 » -> « 2.5 » pour un champ de saisie. */
function days(value: string | null | undefined): string {
  return value === null || value === undefined ? "" : String(Number(value));
}

/** Dates prévues et charges d'une étape (visible seulement avec `PLANIFIER` dans `actions_possibles`). */
export function StepPlanningForm({ step }: { step: Etape }) {
  const update = useUpdateStepPlanning();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<StepPlanningValues>({
    resolver: zodResolver(stepPlanningSchema),
    defaultValues: {
      date_debut_prevue: step.date_debut_prevue ?? "",
      date_fin_prevue: step.date_fin_prevue ?? "",
      charge_prevue_jours: days(step.charge_prevue_jours),
      charge_reelle_jours: days(step.charge_reelle_jours),
    },
  });

  async function onSubmit(values: StepPlanningValues) {
    setFormError(null);
    setSaved(false);
    try {
      await update.mutateAsync({ id: step.id, data: toPlanningPayload(values) });
      setSaved(true);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(onSubmit)(e)}
      noValidate
      aria-labelledby={`planning-${step.id}`}
      className="grid gap-3 rounded-md border border-border p-4 print:hidden"
    >
      <h3 id={`planning-${step.id}`} className="text-base font-semibold">
        {m.planningTitle}
      </h3>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <FormField label={m.plannedStart} error={errors.date_debut_prevue?.message}>
          {(p) => <Input {...p} type="date" {...register("date_debut_prevue")} />}
        </FormField>
        <FormField label={m.plannedEnd} error={errors.date_fin_prevue?.message}>
          {(p) => <Input {...p} type="date" {...register("date_fin_prevue")} />}
        </FormField>
        <FormField label={m.plannedCharge} error={errors.charge_prevue_jours?.message}>
          {(p) => <Input {...p} inputMode="decimal" {...register("charge_prevue_jours")} />}
        </FormField>
        <FormField label={m.actualCharge} error={errors.charge_reelle_jours?.message}>
          {(p) => <Input {...p} inputMode="decimal" {...register("charge_reelle_jours")} />}
        </FormField>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={update.isPending}>
          {fr.common.save}
        </Button>
        {saved && (
          <p role="status" className="text-sm text-text-muted">
            {m.planningSaved}
          </p>
        )}
      </div>
    </form>
  );
}
