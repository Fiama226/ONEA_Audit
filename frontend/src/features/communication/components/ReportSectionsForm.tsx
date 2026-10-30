import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useSaveReport } from "../api";
import { APPRECIATION_LABELS } from "../labels";
import {
  REPORT_FIELDS,
  SECTION_FIELDS,
  reportDefaults,
  reportSchema,
  toReportPayload,
  type ReportFormValues,
} from "../schemas/report";
import type { AppreciationGlobale, Rapport } from "../types";

const t = fr.rapportFinal;

type Props = { rapport: Rapport; readOnly: boolean };

/**
 * Sections textuelles du rapport : enregistrement explicite (« Enregistrer »), jamais automatique.
 * En lecture seule (rapport soumis, validé…), les champs ne sont plus modifiables.
 */
export function ReportSectionsForm({ rapport, readOnly }: Props) {
  const save = useSaveReport();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    control,
    reset,
    formState: { errors },
  } = useForm<ReportFormValues>({
    resolver: zodResolver(reportSchema),
    defaultValues: reportDefaults(rapport),
  });

  const values = useWatch({ control });

  async function onSubmit(values: ReportFormValues) {
    setFormError(null);
    setSaved(false);
    try {
      const updated = await save.mutateAsync({
        id: rapport.id,
        missionId: rapport.mission,
        data: toReportPayload(values),
      });
      reset(reportDefaults(updated));
      setSaved(true);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, REPORT_FIELDS));
    }
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(onSubmit)(e)}
      noValidate
      aria-labelledby="report-sections-title"
      className="grid gap-4"
    >
      <h3 id="report-sections-title" className="text-base font-semibold">
        {t.sectionsTitle}
      </h3>
      {readOnly && <p className="text-sm text-text-muted">{t.sectionsReadOnly}</p>}
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      {SECTION_FIELDS.map((field) => (
        <FormField key={field} label={t.sections[field]} error={errors[field]?.message}>
          {(p) => (
            <>
              <Textarea
                {...p}
                rows={field === "synthese" ? 6 : 4}
                readOnly={readOnly}
                {...register(field)}
              />
              <p className="text-xs text-text-muted tabular-nums" aria-live="off">
                {t.counter.replace("{n}", String((values[field] ?? "").length))}
              </p>
            </>
          )}
        </FormField>
      ))}
      <fieldset
        className="grid gap-2"
        aria-describedby={errors.appreciation_globale ? "appreciation-error" : undefined}
      >
        <legend className="text-sm font-medium">{t.appreciationLegend}</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" value="" disabled={readOnly} {...register("appreciation_globale")} />
          {t.appreciationNone}
        </label>
        {(Object.keys(APPRECIATION_LABELS) as AppreciationGlobale[]).map((value) => (
          <label key={value} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              value={value}
              disabled={readOnly}
              {...register("appreciation_globale")}
            />
            {APPRECIATION_LABELS[value]}
          </label>
        ))}
        {errors.appreciation_globale && (
          <p id="appreciation-error" className="text-sm text-destructive">
            {errors.appreciation_globale.message}
          </p>
        )}
      </fieldset>
      {!readOnly && (
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={save.isPending}>
            {t.save}
          </Button>
          {saved && (
            <p role="status" className="text-sm text-text-muted">
              {t.saved}
            </p>
          )}
        </div>
      )}
    </form>
  );
}
