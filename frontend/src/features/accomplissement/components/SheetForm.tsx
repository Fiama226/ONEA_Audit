import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState, type RefObject } from "react";
import { useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useSaveTestSheet } from "../api";
import { CONCLUSION_LABELS } from "../labels";
import { SHEET_FIELDS, sheetSchema, toSheetPayload, type SheetFormValues } from "../schemas/sheet";
import type { ConclusionTest, FicheDetail } from "../types";

const t = fr.fiches;
const FIRST_RADIO_ID = "fiche-conclusion-first";

/** Pont vers le formulaire : la soumission doit d'abord valider puis enregistrer la saisie. */
export type SheetFormController = { prepareSubmit: () => Promise<boolean> };

type Props = {
  fiche: FicheDetail;
  editable: boolean;
  controllerRef?: RefObject<SheetFormController | null>;
};

function defaults(fiche: FicheDetail): SheetFormValues {
  return {
    date_realisation: fiche.date_realisation ?? "",
    travaux_realises: fiche.travaux_realises ?? "",
    echantillon_teste: fiche.echantillon_teste ?? "",
    taille_testee: fiche.taille_testee == null ? "" : String(fiche.taille_testee),
    nombre_exceptions: fiche.nombre_exceptions == null ? "" : String(fiche.nombre_exceptions),
    resultat: fiche.resultat ?? "",
    conclusion: (fiche.conclusion ?? "") as SheetFormValues["conclusion"],
    commentaire_conclusion: fiche.commentaire_conclusion ?? "",
    charge_reelle_jours:
      fiche.charge_reelle_jours == null ? "" : String(fiche.charge_reelle_jours).replace(".", ","),
    justification_sans_piece: fiche.justification_sans_piece ?? "",
  };
}

/** Formulaire de la fiche (champs de D7) ; en lecture seule hors des droits MODIFIER. */
export function SheetForm({ fiche, editable, controllerRef }: Props) {
  const save = useSaveTestSheet();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    getValues,
    trigger,
    formState: { errors },
  } = useForm<SheetFormValues>({
    resolver: zodResolver(sheetSchema),
    defaultValues: defaults(fiche),
  });

  async function persist(values: SheetFormValues): Promise<boolean> {
    setFormError(null);
    setSaved(false);
    try {
      await save.mutateAsync({
        id: fiche.id,
        missionId: fiche.mission,
        data: toSheetPayload(values),
      });
      return true;
    } catch (e) {
      setFormError(applyApiErrors(e, setError, SHEET_FIELDS));
      return false;
    }
  }

  async function onSubmit(values: SheetFormValues) {
    if (await persist(values)) setSaved(true);
  }

  useEffect(() => {
    if (!controllerRef) return;
    controllerRef.current = {
      prepareSubmit: async () => {
        if (!editable) return true;
        if (!(await trigger(undefined, { shouldFocus: true }))) return false;
        if (getValues("conclusion") === "") {
          setError("conclusion", { type: "client", message: t.conclusionRequired });
          document.getElementById(FIRST_RADIO_ID)?.focus();
          return false;
        }
        return persist(getValues());
      },
    };
  });

  const conclusionError = errors.conclusion?.message;
  const conclusionErrorId = "fiche-conclusion-error";
  const conclusionHelpId = "fiche-conclusion-help";

  return (
    <form
      onSubmit={(e) => void handleSubmit(onSubmit)(e)}
      noValidate
      aria-label={t.formTitle}
      className="grid gap-4"
    >
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      {!editable && <p className="text-sm text-text-muted print:hidden">{t.readOnly}</p>}
      <fieldset disabled={!editable} className="grid gap-4">
        <FormField label={t.dateDone} error={errors.date_realisation?.message}>
          {(p) => <Input {...p} type="date" {...register("date_realisation")} />}
        </FormField>
        <FormField label={t.work} error={errors.travaux_realises?.message}>
          {(p) => <Textarea {...p} rows={4} {...register("travaux_realises")} />}
        </FormField>
        <FormField label={t.sampleTested} error={errors.echantillon_teste?.message}>
          {(p) => <Textarea {...p} rows={2} {...register("echantillon_teste")} />}
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label={t.sizeTested} error={errors.taille_testee?.message}>
            {(p) => <Input {...p} inputMode="numeric" {...register("taille_testee")} />}
          </FormField>
          <FormField label={t.exceptions} error={errors.nombre_exceptions?.message}>
            {(p) => <Input {...p} inputMode="numeric" {...register("nombre_exceptions")} />}
          </FormField>
        </div>
        <FormField label={t.result} error={errors.resultat?.message}>
          {(p) => <Textarea {...p} rows={4} {...register("resultat")} />}
        </FormField>
        <fieldset
          className="grid gap-2"
          aria-describedby={[conclusionHelpId, conclusionError ? conclusionErrorId : null]
            .filter(Boolean)
            .join(" ")}
        >
          <legend className="text-sm font-medium">{t.conclusionLegend}</legend>
          <p id={conclusionHelpId} className="text-xs text-text-muted">
            {t.conclusionHelp}
          </p>
          {(Object.keys(CONCLUSION_LABELS) as ConclusionTest[]).map((value, index) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                id={index === 0 ? FIRST_RADIO_ID : undefined}
                value={value}
                {...register("conclusion")}
              />
              {CONCLUSION_LABELS[value]}
            </label>
          ))}
          {conclusionError && (
            <p id={conclusionErrorId} className="text-sm text-destructive">
              {conclusionError}
            </p>
          )}
        </fieldset>
        <FormField label={t.conclusionComment} error={errors.commentaire_conclusion?.message}>
          {(p) => <Textarea {...p} rows={3} {...register("commentaire_conclusion")} />}
        </FormField>
        <FormField label={t.realCharge} error={errors.charge_reelle_jours?.message}>
          {(p) => <Input {...p} inputMode="decimal" {...register("charge_reelle_jours")} />}
        </FormField>
        <FormField
          label={t.noEvidenceReason}
          help={t.noEvidenceHelp}
          error={errors.justification_sans_piece?.message}
        >
          {(p) => <Textarea {...p} rows={3} {...register("justification_sans_piece")} />}
        </FormField>
      </fieldset>
      {editable && (
        <div className="flex items-center gap-3 print:hidden">
          <Button type="submit" disabled={save.isPending}>
            {t.saveDraft}
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
