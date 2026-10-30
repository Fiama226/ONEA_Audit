import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useMissionRisks } from "@/features/missions/api";
import { fr } from "@/i18n/fr";
import { useSavePlannedTest } from "../api";
import { METHODE_SELECTION_LABELS, NATURE_TEST_LABELS } from "../labels";
import {
  EMPTY_PLANNED_TEST,
  METHODES,
  NATURES,
  plannedTestSchema,
  toPlannedTestInput,
  type PlannedTestFormValues,
} from "../schemas/plannedTest";

const t = fr.programme;

const FIELDS = [
  "libelle",
  "objectif_test",
  "nature",
  "procedure",
  "population",
  "taille_echantillon",
  "methode_selection",
  "risque_mission",
] as const;

type Props = {
  missionId: string;
  /** Programme cible ; `null` : boîte fermée. */
  target: { programmeId: string; code: string } | null;
  onOpenChange: (open: boolean) => void;
};

export function PlannedTestDialog({ missionId, target, onOpenChange }: Props) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        {target && (
          <PlannedTestForm
            missionId={missionId}
            programmeId={target.programmeId}
            code={target.code}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function PlannedTestForm({
  missionId,
  programmeId,
  code,
  onDone,
}: {
  missionId: string;
  programmeId: string;
  code: string;
  onDone: () => void;
}) {
  const save = useSavePlannedTest();
  const risks = useMissionRisks(missionId);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PlannedTestFormValues>({
    resolver: zodResolver(plannedTestSchema),
    defaultValues: EMPTY_PLANNED_TEST,
  });

  async function submit(values: PlannedTestFormValues) {
    setFormError(null);
    try {
      await save.mutateAsync({ missionId, data: toPlannedTestInput(programmeId, values) });
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t.testTitle}</DialogTitle>
        <DialogDescription>
          {t.testDescription}
          {code}.
        </DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.fieldLabel} error={errors.libelle?.message}>
        {(p) => <Input {...p} maxLength={300} required {...register("libelle")} />}
      </FormField>
      <FormField label={t.fieldObjective} error={errors.objectif_test?.message}>
        {(p) => <Textarea {...p} rows={2} {...register("objectif_test")} />}
      </FormField>
      <FormField label={t.fieldNature} error={errors.nature?.message}>
        {(p) => (
          <NativeSelect {...p} required {...register("nature")}>
            <option value="">{t.choose}</option>
            {NATURES.map((n) => (
              <option key={n} value={n}>
                {NATURE_TEST_LABELS[n]}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>
      <FormField label={t.fieldProcedure} error={errors.procedure?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("procedure")} />}
      </FormField>
      <FormField label={t.fieldPopulation} error={errors.population?.message}>
        {(p) => <Input {...p} {...register("population")} />}
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t.fieldSize} error={errors.taille_echantillon?.message}>
          {(p) => <Input {...p} inputMode="numeric" {...register("taille_echantillon")} />}
        </FormField>
        <FormField label={t.fieldMethod} error={errors.methode_selection?.message}>
          {(p) => (
            <NativeSelect {...p} {...register("methode_selection")}>
              <option value="">{t.none}</option>
              {METHODES.map((m) => (
                <option key={m} value={m}>
                  {METHODE_SELECTION_LABELS[m]}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
      </div>
      <FormField
        label={t.fieldRisk}
        error={errors.risque_mission?.message ?? (risks.isError ? t.risksLoadError : undefined)}
      >
        {(p) => (
          <NativeSelect {...p} {...register("risque_mission")}>
            <option value="">{t.none}</option>
            {(risks.data?.results ?? []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.libelle || r.code_source}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {t.saveTest}
        </Button>
      </DialogFooter>
    </form>
  );
}
