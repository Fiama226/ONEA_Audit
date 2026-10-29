import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useOrientationReport, useSaveOrientationReport } from "../api";
import { COUVERTURE_ORDRE_LABELS, VARIANTE_ORIENTATION_LABELS } from "../labels";
import {
  orientationReportSchema,
  type OrientationReportFormValues,
} from "../schemas/orientationReport";
import type { CouvertureOrdre, RapportOrientation, VarianteOrientation } from "../types";

const t = fr.analyseVII;

const FIELDS = [
  "variante",
  "contexte",
  "approche",
  "observations",
  "couverture_ordre",
  "justification_couverture",
] as const;

export function OrientationReportForm({
  missionId,
  editable,
}: {
  missionId: string;
  editable: boolean;
}) {
  const report = useOrientationReport(missionId);
  if (report.isPending) return <p role="status">{fr.common.loading}</p>;
  if (report.isError)
    return (
      <p role="alert" className={ALERT_CLASS}>
        {fr.analyse.loadError}
      </p>
    );
  return <ReportForm missionId={missionId} report={report.data} editable={editable} />;
}

function Recall({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-medium">{label}</dt>
      <dd className="whitespace-pre-line text-text-muted">{value || fr.analyseVII.noControl}</dd>
    </div>
  );
}

function ReportForm({
  missionId,
  report,
  editable,
}: {
  missionId: string;
  report: RapportOrientation;
  editable: boolean;
}) {
  const save = useSaveOrientationReport();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<OrientationReportFormValues>({
    resolver: zodResolver(orientationReportSchema),
    defaultValues: {
      variante: report.variante ?? "COMPLET",
      contexte: report.contexte ?? "",
      approche: report.approche ?? "",
      observations: report.observations ?? "",
      couverture_ordre: report.couverture_ordre ?? "",
      justification_couverture: report.justification_couverture ?? "",
    },
  });

  async function submit(values: OrientationReportFormValues) {
    setFormError(null);
    setSaved(false);
    try {
      const data =
        values.couverture_ordre === "EXACTE" ? { ...values, justification_couverture: "" } : values;
      await save.mutateAsync({ missionId, data });
      setSaved(true);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  const rappel = report.rappel_ordre;
  return (
    <form
      onSubmit={(e) => void handleSubmit(submit)(e)}
      noValidate
      onChange={() => setSaved(false)}
      aria-labelledby={`report-${missionId}`}
      className="grid gap-4"
    >
      <h4 id={`report-${missionId}`} className="font-semibold">
        {t.reportTitle}
      </h4>
      {!editable && <p className="text-sm text-text-muted">{t.readOnly}</p>}
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <fieldset disabled={!editable} className="grid gap-4">
        <Controller
          control={control}
          name="variante"
          render={({ field }) => (
            <FormField label={t.variantLabel} error={errors.variante?.message}>
              {(p) => (
                <NativeSelect
                  {...p}
                  name={field.name}
                  ref={field.ref}
                  value={field.value}
                  onBlur={field.onBlur}
                  onChange={(e) => field.onChange(e.target.value)}
                >
                  {(Object.keys(VARIANTE_ORIENTATION_LABELS) as VarianteOrientation[]).map((k) => (
                    <option key={k} value={k}>
                      {VARIANTE_ORIENTATION_LABELS[k]}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
          )}
        />
        <FormField label={t.contextLabel} error={errors.contexte?.message}>
          {(p) => <Textarea {...p} rows={4} {...register("contexte")} />}
        </FormField>
        <FormField label={t.approachLabel} error={errors.approche?.message}>
          {(p) => <Textarea {...p} rows={4} {...register("approche")} />}
        </FormField>
        <section aria-labelledby={`recon-${missionId}`} className="grid gap-3">
          <h5 id={`recon-${missionId}`} className="text-sm font-semibold">
            {t.reconciliationTitle}
          </h5>
          <dl className="grid gap-2 rounded-md border border-border p-3 text-sm">
            <Recall label={t.orderObjectives} value={rappel.objectifs} />
            <Recall label={t.orderScope} value={rappel.perimetre} />
            <Recall label={t.orderExclusions} value={rappel.exclusions} />
          </dl>
          <Controller
            control={control}
            name="couverture_ordre"
            render={({ field }) => (
              <FormField label={t.coverageLabel} error={errors.couverture_ordre?.message}>
                {(p) => (
                  <NativeSelect
                    {...p}
                    name={field.name}
                    ref={field.ref}
                    value={field.value}
                    onBlur={field.onBlur}
                    onChange={(e) => field.onChange(e.target.value)}
                  >
                    <option value="">{t.coveragePlaceholder}</option>
                    {(Object.keys(COUVERTURE_ORDRE_LABELS) as CouvertureOrdre[]).map((k) => (
                      <option key={k} value={k}>
                        {COUVERTURE_ORDRE_LABELS[k]}
                      </option>
                    ))}
                  </NativeSelect>
                )}
              </FormField>
            )}
          />
          <FormField
            label={t.coverageJustificationLabel}
            error={errors.justification_couverture?.message}
          >
            {(p) => <Textarea {...p} rows={3} {...register("justification_couverture")} />}
          </FormField>
        </section>
        <FormField label={t.observationsLabel} error={errors.observations?.message}>
          {(p) => <Textarea {...p} rows={3} {...register("observations")} />}
        </FormField>
      </fieldset>
      {editable && (
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={save.isPending}>
            {t.saveReport}
          </Button>
          {saved && <p role="status">{t.saved}</p>}
        </div>
      )}
    </form>
  );
}
