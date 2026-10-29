import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
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
import { fr } from "@/i18n/fr";
import { useSaveMissionRisk } from "../api";
import {
  newMissionRiskSchema,
  reevaluateMissionRiskSchema,
  riskPreview,
  type NewMissionRiskValues,
  type ReevaluateMissionRiskValues,
} from "../schemas/missionRisk";
import type { Mission, RisqueMission } from "../types";

const m = fr.missionEtapes;
const SCALE = ["1", "2", "3", "4", "5"] as const;

type Props = {
  mission: Mission;
  /** Risque à réévaluer ; absent pour la création d'un risque nouveau. */
  risk?: RisqueMission;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function MissionRiskDialog({ mission, risk, open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {open &&
          (risk ? (
            <ReevaluateForm risk={risk} onDone={() => onOpenChange(false)} />
          ) : (
            <NewRiskForm mission={mission} onDone={() => onOpenChange(false)} />
          ))}
      </DialogContent>
    </Dialog>
  );
}

function ScaleSelect({
  p,
  ...props
}: {
  p: { id: string; "aria-invalid": boolean; "aria-describedby": string | undefined };
} & React.ComponentProps<"select">) {
  return (
    <NativeSelect {...p} {...props}>
      <option value="">{m.choose}</option>
      {SCALE.map((v) => (
        <option key={v} value={v}>
          {v}
        </option>
      ))}
    </NativeSelect>
  );
}

function Preview({ probabilite, impact }: { probabilite: string; impact: string }) {
  const text = riskPreview(probabilite, impact);
  return (
    <p role="status" className="min-h-5 text-sm font-medium">
      {text}
    </p>
  );
}

function Footer({ pending, onCancel }: { pending: boolean; onCancel: () => void }) {
  return (
    <DialogFooter>
      <Button type="button" variant="outline" onClick={onCancel}>
        {fr.common.cancel}
      </Button>
      <Button type="submit" disabled={pending}>
        {fr.common.save}
      </Button>
    </DialogFooter>
  );
}

function NewRiskForm({ mission, onDone }: { mission: Mission; onDone: () => void }) {
  const save = useSaveMissionRisk();
  const [formError, setFormError] = useState<string | null>(null);
  const processes = mission.processus_detail;
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<NewMissionRiskValues>({
    resolver: zodResolver(newMissionRiskSchema),
    defaultValues: {
      processus: processes.length === 1 ? (processes[0]?.id ?? "") : "",
      libelle: "",
      description: "",
      probabilite: "",
      impact: "",
    },
  });
  const [probValue, impactValue] = useWatch({ control, name: ["probabilite", "impact"] });

  async function onSubmit(values: NewMissionRiskValues) {
    setFormError(null);
    try {
      await save.mutateAsync({
        data: {
          mission: mission.id,
          processus: values.processus,
          libelle: values.libelle,
          description: values.description,
          probabilite: Number(values.probabilite),
          impact: Number(values.impact),
        },
      });
      onDone();
    } catch (e) {
      setFormError(
        applyApiErrors(e, setError, [
          "processus",
          "libelle",
          "description",
          "probabilite",
          "impact",
        ]),
      );
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{m.newRiskTitle}</DialogTitle>
        <DialogDescription className="sr-only">{m.newRiskTitle}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={m.fieldProcess} error={errors.processus?.message}>
        {(p) => (
          <NativeSelect {...p} {...register("processus")}>
            <option value="">{m.choose}</option>
            {processes.map((pr) => (
              <option key={pr.id} value={pr.id}>
                {pr.code} — {pr.libelle}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>
      <FormField label={m.fieldLabel} error={errors.libelle?.message}>
        {(p) => <Input {...p} maxLength={500} {...register("libelle")} />}
      </FormField>
      <FormField label={m.fieldDescription} error={errors.description?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("description")} />}
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label={m.fieldProbability} error={errors.probabilite?.message}>
          {(p) => <ScaleSelect p={p} {...register("probabilite")} />}
        </FormField>
        <FormField label={m.fieldImpact} error={errors.impact?.message}>
          {(p) => <ScaleSelect p={p} {...register("impact")} />}
        </FormField>
      </div>
      <Preview probabilite={probValue} impact={impactValue} />
      <Footer pending={save.isPending} onCancel={onDone} />
    </form>
  );
}

function ReevaluateForm({ risk, onDone }: { risk: RisqueMission; onDone: () => void }) {
  const save = useSaveMissionRisk();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<ReevaluateMissionRiskValues>({
    resolver: zodResolver(reevaluateMissionRiskSchema),
    defaultValues: {
      probabilite: String(risk.probabilite ?? ""),
      impact: String(risk.impact ?? ""),
      commentaire: risk.commentaire ?? "",
    },
  });
  const [probValue, impactValue] = useWatch({ control, name: ["probabilite", "impact"] });

  async function onSubmit(values: ReevaluateMissionRiskValues) {
    setFormError(null);
    try {
      await save.mutateAsync({
        id: risk.id,
        data: {
          probabilite: Number(values.probabilite),
          impact: Number(values.impact),
          commentaire: values.commentaire,
        },
      });
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["probabilite", "impact", "commentaire"]));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{m.reevaluateTitle}</DialogTitle>
        <DialogDescription>{risk.libelle}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <div className="grid grid-cols-2 gap-3">
        <FormField label={m.fieldProbability} error={errors.probabilite?.message}>
          {(p) => <ScaleSelect p={p} {...register("probabilite")} />}
        </FormField>
        <FormField label={m.fieldImpact} error={errors.impact?.message}>
          {(p) => <ScaleSelect p={p} {...register("impact")} />}
        </FormField>
      </div>
      <Preview probabilite={probValue} impact={impactValue} />
      <FormField label={m.fieldComment} error={errors.commentaire?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("commentaire")} />}
      </FormField>
      <Footer pending={save.isPending} onCancel={onDone} />
    </form>
  );
}
