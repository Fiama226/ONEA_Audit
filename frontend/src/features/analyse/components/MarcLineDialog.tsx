import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { useAuditableTree } from "@/features/referentiel/api";
import { fr } from "@/i18n/fr";
import { useSaveMarcLine } from "../api";
import { COMPOSANTE_LABELS, EVALUATION_CONCEPTION_LABELS, NATURE_CONTROLE_LABELS } from "../labels";
import { marcLineSchema, type MarcLineFormValues } from "../schemas/marcLine";
import type { Composante, EvaluationConception, LigneMarc, NatureControle } from "../types";

const t = fr.analyseVVI;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  missionId: string;
  /** Ligne à modifier ; absente pour un ajout. */
  line?: LigneMarc;
};

export function MarcLineDialog({ open, onOpenChange, ...rest }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <MarcLineForm {...rest} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function MarcLineForm({
  missionId,
  line,
  onDone,
}: Omit<Props, "open" | "onOpenChange"> & { onDone: () => void }) {
  const save = useSaveMarcLine();
  const risks = useMissionRisks(missionId);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<MarcLineFormValues>({
    resolver: zodResolver(marcLineSchema),
    defaultValues: {
      risque: line?.risque ?? "",
      objet_auditable: line?.objet_auditable ?? "",
      operation: line?.operation ?? "",
      objectif_controle: line?.objectif_controle ?? "",
      controle_attendu: line?.controle_attendu ?? "",
      controle_existant: line?.controle_existant ?? "",
      composante: line?.composante ?? "",
      nature: line?.nature ?? "",
      evaluation: line?.evaluation ?? "",
      cle: line?.cle ?? false,
      commentaire: line?.commentaire ?? "",
    },
  });
  const riskId = useWatch({ control, name: "risque" });
  const processId = risks.data?.results.find((r) => r.id === riskId)?.processus;
  const tree = useAuditableTree(processId);
  const auditables = (tree.data ?? []).flatMap((d) => [d, ...d.operations]);
  const prefilled =
    line !== undefined &&
    (line.objet_auditable !== null || line.operation !== "" || line.objectif_controle !== "");

  async function onSubmit(values: MarcLineFormValues) {
    setFormError(null);
    const data = {
      mission: missionId,
      risque: values.risque,
      objet_auditable: values.objet_auditable === "" ? null : values.objet_auditable,
      operation: values.operation,
      objectif_controle: values.objectif_controle,
      controle_attendu: values.controle_attendu,
      controle_existant: values.controle_existant,
      composante: values.composante,
      nature: values.nature,
      evaluation: values.evaluation,
      cle: values.cle,
      commentaire: values.commentaire,
    };
    try {
      await save.mutateAsync(line ? { id: line.id, data } : { data });
      onDone();
    } catch (e) {
      setFormError(
        applyApiErrors(e, setError, [
          "risque",
          "objet_auditable",
          "operation",
          "objectif_controle",
          "controle_attendu",
          "controle_existant",
          "composante",
          "nature",
          "evaluation",
          "cle",
          "commentaire",
        ]),
      );
    }
  }

  const help = prefilled ? t.prefilled : undefined;

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{line ? t.editControl : t.addControl}</DialogTitle>
        <DialogDescription>{t.lineDialogDesc}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      {risks.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {t.risksError}
        </p>
      )}
      <Controller
        control={control}
        name="risque"
        render={({ field }) => (
          <FormField label={t.riskLabel} error={errors.risque?.message}>
            {(p) => (
              <NativeSelect
                {...p}
                required
                name={field.name}
                ref={field.ref}
                value={field.value}
                onBlur={field.onBlur}
                onChange={(e) => field.onChange(e.target.value)}
                disabled={risks.isPending}
                aria-busy={risks.isPending}
              >
                <option value="">{risks.isPending ? t.risksLoading : t.riskPlaceholder}</option>
                {(risks.data?.results ?? []).map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.code_source} · {r.libelle}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        )}
      />
      <Controller
        control={control}
        name="objet_auditable"
        render={({ field }) => (
          <FormField label={t.auditableLabel} error={errors.objet_auditable?.message} help={help}>
            {(p) => (
              <NativeSelect
                {...p}
                name={field.name}
                ref={field.ref}
                value={field.value}
                onBlur={field.onBlur}
                onChange={(e) => field.onChange(e.target.value)}
              >
                <option value="">{t.noAuditable}</option>
                {auditables.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.libelle}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        )}
      />
      <FormField label={t.operationLabel} error={errors.operation?.message} help={help}>
        {(p) => <Input {...p} maxLength={300} {...register("operation")} />}
      </FormField>
      <FormField label={t.objectiveLabel} error={errors.objectif_controle?.message} help={help}>
        {(p) => <Textarea {...p} rows={2} {...register("objectif_controle")} />}
      </FormField>
      <FormField label={t.expectedLabel} error={errors.controle_attendu?.message}>
        {(p) => <Textarea {...p} rows={2} {...register("controle_attendu")} />}
      </FormField>
      <FormField label={t.existingLabel} error={errors.controle_existant?.message}>
        {(p) => <Textarea {...p} rows={2} {...register("controle_existant")} />}
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <Controller
          control={control}
          name="composante"
          render={({ field }) => (
            <FormField label={t.componentLabel} error={errors.composante?.message}>
              {(p) => (
                <NativeSelect
                  {...p}
                  name={field.name}
                  ref={field.ref}
                  value={field.value}
                  onBlur={field.onBlur}
                  onChange={(e) => field.onChange(e.target.value)}
                >
                  <option value="">{t.choose}</option>
                  {(Object.keys(COMPOSANTE_LABELS) as Composante[]).map((k) => (
                    <option key={k} value={k}>
                      {COMPOSANTE_LABELS[k]}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
          )}
        />
        <Controller
          control={control}
          name="nature"
          render={({ field }) => (
            <FormField label={t.natureLabel} error={errors.nature?.message}>
              {(p) => (
                <NativeSelect
                  {...p}
                  name={field.name}
                  ref={field.ref}
                  value={field.value}
                  onBlur={field.onBlur}
                  onChange={(e) => field.onChange(e.target.value)}
                >
                  <option value="">{t.choose}</option>
                  {(Object.keys(NATURE_CONTROLE_LABELS) as NatureControle[]).map((k) => (
                    <option key={k} value={k}>
                      {NATURE_CONTROLE_LABELS[k]}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
          )}
        />
      </div>
      <Controller
        control={control}
        name="evaluation"
        render={({ field }) => (
          <FormField label={t.evaluationLabel} error={errors.evaluation?.message}>
            {(p) => (
              <NativeSelect
                {...p}
                name={field.name}
                ref={field.ref}
                value={field.value}
                onBlur={field.onBlur}
                onChange={(e) => field.onChange(e.target.value)}
              >
                <option value="">{t.choose}</option>
                {(Object.keys(EVALUATION_CONCEPTION_LABELS) as EvaluationConception[]).map((k) => (
                  <option key={k} value={k}>
                    {EVALUATION_CONCEPTION_LABELS[k]}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        )}
      />
      <Controller
        control={control}
        name="cle"
        render={({ field }) => (
          <FormField label={t.keyLabel} error={errors.cle?.message}>
            {(p) => (
              <Checkbox
                id={p.id}
                aria-invalid={p["aria-invalid"]}
                aria-describedby={p["aria-describedby"]}
                checked={field.value}
                onCheckedChange={(c) => field.onChange(c === true)}
              />
            )}
          </FormField>
        )}
      />
      <FormField label={t.commentLabel} error={errors.commentaire?.message}>
        {(p) => <Textarea {...p} rows={2} {...register("commentaire")} />}
      </FormField>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          {fr.common.cancel}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {fr.common.save}
        </Button>
      </DialogFooter>
    </form>
  );
}
