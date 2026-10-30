import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RiskLevelBadge } from "@/features/referentiel/components/RiskLevelBadge";
import { NIVEAU_LABELS } from "@/features/referentiel/labels";
import { niveauFromScore } from "@/features/referentiel/schemas/risk";
import { useMissionRisks } from "@/features/missions/api";
import type { Mission } from "@/features/missions/types";
import { fr } from "@/i18n/fr";
import { useSaveFinding } from "../api";
import {
  CONSTAT_FIELDS,
  constatSchema,
  defaultConstatValues,
  toConstatPayload,
  type ConstatFormValues,
} from "../schemas/constat";
import type { Constat } from "../types";
import { CausesEditor } from "./CausesEditor";
import { ConstatActions } from "./ConstatActions";
import { RecommandationsEditor } from "./RecommandationsEditor";

const t = fr.constatsUi;
const SCALE = ["1", "2", "3", "4", "5"];

export type FicheOption = { id: string; test_code: string };

type Props = {
  mission: Mission;
  constat?: Constat;
  /** Fiches ANOMALIE validées de la mission (cases de liaison). */
  fiches: FicheOption[];
  editable: boolean;
  prefill?: Partial<ConstatFormValues>;
  onSaved: (constat: Constat) => void;
  onDeleted: () => void;
};

type Option = { id: string; code: string; libelle: string };

function withCurrent(options: Option[], current: Option | undefined): Option[] {
  if (!current || options.some((o) => o.id === current.id)) return options;
  return [...options, current];
}

/** Formulaire du constat (création, édition ou lecture seule) et actions du serveur. */
export function ConstatForm({
  mission,
  constat,
  fiches,
  editable,
  prefill,
  onSaved,
  onDeleted,
}: Props) {
  const save = useSaveFinding();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isDirty },
  } = useForm<ConstatFormValues>({
    resolver: zodResolver(constatSchema),
    defaultValues: defaultConstatValues(constat, prefill),
  });
  const [probabilite, impact] = useWatch({ control, name: ["probabilite", "impact"] });

  const entites = withCurrent(mission.entites_detail, constat?.entite_detail);
  const processus = withCurrent(mission.processus_detail, constat?.processus_detail);
  const score = probabilite && impact ? Number(probabilite) * Number(impact) : null;
  const niveau = score === null ? null : niveauFromScore(score);

  async function submit(values: ConstatFormValues) {
    setFormError(null);
    setSaved(false);
    const data = toConstatPayload(mission.id, values);
    try {
      const result =
        constat === undefined
          ? await save.mutateAsync({ missionId: mission.id, data })
          : await save.mutateAsync({ missionId: mission.id, id: constat.id, data });
      reset(defaultConstatValues(result));
      setSaved(true);
      onSaved(result);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, CONSTAT_FIELDS));
    }
  }

  function actionError(e: unknown): string | null {
    return applyApiErrors(e, setError, CONSTAT_FIELDS);
  }

  return (
    <div className="grid gap-6">
      <form
        onSubmit={(e) => void handleSubmit(submit)(e)}
        noValidate
        onChange={() => setSaved(false)}
        aria-label={constat ? constat.reference : t.pageTitleNew}
        className="grid gap-6"
      >
        {formError && (
          <p role="alert" className={ALERT_CLASS}>
            {formError}
          </p>
        )}
        {!editable && <p className="text-sm text-text-muted">{t.readOnly}</p>}
        <fieldset disabled={!editable} className="grid gap-4">
          <FormField label={t.fieldTitle} error={errors.titre?.message}>
            {(p) => <Input {...p} {...register("titre")} />}
          </FormField>
          {(editable || (constat?.fiches_detail?.length ?? 0) > 0) && (
            <fieldset className="grid gap-2">
              <legend className="text-sm font-medium">{t.fieldFiches}</legend>
              {editable ? (
                fiches.length === 0 ? (
                  <p className="text-sm text-text-muted">{t.noFiches}</p>
                ) : (
                  fiches.map((f) => (
                    <label key={f.id} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" value={f.id} {...register("fiches")} />
                      {t.ficheLabel.replace("{code}", f.test_code)}
                    </label>
                  ))
                )
              ) : (
                <ul className="list-disc pl-5 text-sm">
                  {constat?.fiches_detail?.map((f) => (
                    <li key={f.id}>{t.ficheLabel.replace("{code}", f.test_code)}</li>
                  ))}
                </ul>
              )}
            </fieldset>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            <FormField label={t.fieldEntity} error={errors.entite?.message}>
              {(p) => (
                <NativeSelect {...p} required {...register("entite")}>
                  <option value="">{t.placeholderSelect}</option>
                  {entites.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.code} · {o.libelle}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <FormField label={t.fieldProcess} error={errors.processus?.message}>
              {(p) => (
                <NativeSelect {...p} required {...register("processus")}>
                  <option value="">{t.placeholderSelect}</option>
                  {processus.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.code} · {o.libelle}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
          </div>
          {editable && (
            <RiskField
              missionId={mission.id}
              register={register}
              error={errors.risque_mission?.message}
            />
          )}
          <FormField label={t.fieldFact} error={errors.fait_constate?.message}>
            {(p) => <Textarea {...p} rows={4} {...register("fait_constate")} />}
          </FormField>
          <FormField label={t.fieldReference} error={errors.referentiel?.message}>
            {(p) => <Textarea {...p} rows={3} {...register("referentiel")} />}
          </FormField>
          <FormField label={t.fieldConsequence} error={errors.consequence?.message}>
            {(p) => <Textarea {...p} rows={3} {...register("consequence")} />}
          </FormField>
          <FormField label={t.fieldConclusion} error={errors.conclusion?.message}>
            {(p) => <Textarea {...p} rows={3} {...register("conclusion")} />}
          </FormField>
          <div className="grid items-end gap-4 md:grid-cols-3">
            <FormField label={t.fieldProbability} error={errors.probabilite?.message}>
              {(p) => (
                <NativeSelect {...p} {...register("probabilite")}>
                  <option value="">{t.noValue}</option>
                  {SCALE.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <FormField label={t.fieldImpact} error={errors.impact?.message}>
              {(p) => (
                <NativeSelect {...p} {...register("impact")}>
                  <option value="">{t.noValue}</option>
                  {SCALE.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <div className="grid gap-1 text-sm" aria-live="polite">
              {score !== null && niveau !== null ? (
                <>
                  <span className="font-medium tabular-nums">
                    {t.scorePreview
                      .replace("{score}", String(score))
                      .replace("{niveau}", NIVEAU_LABELS[niveau])}
                  </span>
                  <RiskLevelBadge niveau={niveau} className="justify-self-start" />
                </>
              ) : (
                <span className="text-text-muted">{t.noValue}</span>
              )}
              <span className="text-xs text-text-muted">{t.scoreNote}</span>
            </div>
          </div>
          <CausesEditor control={control} register={register} editable={editable} />
          <RecommandationsEditor control={control} register={register} editable={editable} />
        </fieldset>
        {editable && (
          <div className="flex items-center gap-3 print:hidden">
            <Button type="submit" disabled={save.isPending}>
              {t.save}
            </Button>
            {saved && <p role="status">{t.saved}</p>}
          </div>
        )}
      </form>
      {constat && (
        <>
          {isDirty && editable && <p className="text-sm text-text-muted">{t.unsavedNote}</p>}
          <ConstatActions constat={constat} onError={actionError} onDeleted={onDeleted} />
        </>
      )}
    </div>
  );
}

function RiskField({
  missionId,
  register,
  error,
}: {
  missionId: string;
  register: ReturnType<typeof useForm<ConstatFormValues>>["register"];
  error: string | undefined;
}) {
  const risks = useMissionRisks(missionId);
  return (
    <FormField label={t.fieldRisk} error={error}>
      {(p) => (
        <NativeSelect {...p} {...register("risque_mission")}>
          <option value="">{t.noRisk}</option>
          {risks.data?.results.map((r) => (
            <option key={r.id} value={r.id}>
              {r.processus_code} · {r.libelle}
            </option>
          ))}
        </NativeSelect>
      )}
    </FormField>
  );
}
