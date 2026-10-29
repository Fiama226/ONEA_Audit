import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useSaveInterview, useSteps } from "../api";
import { fromLocalInput, toLocalInput } from "../schemas/datetime";
import { interviewSchema, type InterviewFormValues } from "../schemas/interview";
import type { Entretien, Mission } from "../types";
import { UserPicker } from "./UserPicker";

const t = fr.missionTravaux;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mission: Mission;
  /** Entretien à modifier ; absent pour une planification. */
  interview?: Entretien;
  /** Étape présélectionnée à la création. */
  defaultStep?: string;
};

export function InterviewFormDialog({ open, onOpenChange, ...rest }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <InterviewForm {...rest} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

/** Auditeurs : uniquement l'équipe de la mission (hors audités). */
function AuditorChoice({
  mission,
  value,
  onChange,
}: {
  mission: Mission;
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const baseId = useId();
  const team = mission.equipe.filter((a) => a.role_mission !== "AUDITE");
  return (
    <fieldset className="grid gap-2">
      <legend className="text-sm font-medium">{t.auditorsLabel}</legend>
      {team.length === 0 ? (
        <p className="text-sm text-text-muted">{t.auditorsNone}</p>
      ) : (
        <ul className="rounded-md border border-border">
          {team.map((a) => {
            const id = String(a.utilisateur);
            const inputId = `${baseId}-${id}`;
            return (
              <li key={a.id} className="flex items-center gap-2 px-3 py-2 text-sm">
                <Checkbox
                  id={inputId}
                  checked={value.includes(id)}
                  onCheckedChange={(checked) =>
                    onChange(checked === true ? [...value, id] : value.filter((v) => v !== id))
                  }
                />
                <Label htmlFor={inputId} className="font-normal">
                  {a.utilisateur_detail.nom_complet}
                </Label>
              </li>
            );
          })}
        </ul>
      )}
    </fieldset>
  );
}

function InterviewForm({
  mission,
  interview,
  defaultStep,
  onDone,
}: Omit<Props, "open" | "onOpenChange"> & { onDone: () => void }) {
  const save = useSaveInterview();
  const steps = useSteps(mission.id);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<InterviewFormValues>({
    resolver: zodResolver(interviewSchema),
    defaultValues: {
      objet: interview?.objet ?? "",
      date_prevue: interview ? toLocalInput(interview.date_prevue) : "",
      duree_minutes: interview?.duree_minutes != null ? String(interview.duree_minutes) : "",
      lieu: interview?.lieu ?? "",
      etape: interview?.etape ?? defaultStep ?? "",
      auditeurs: (interview?.auditeurs ?? []).map(String),
      interlocuteurs: (interview?.interlocuteurs ?? []).map(String),
      autres_interlocuteurs: interview?.autres_interlocuteurs ?? "",
      themes: interview?.themes ?? "",
      compte_rendu: interview?.compte_rendu ?? "",
      note_synthese: interview?.note_synthese ?? "",
    },
  });

  async function onSubmit(values: InterviewFormValues) {
    setFormError(null);
    const optional = (key: string, value: string) =>
      interview || value.trim() !== "" ? { [key]: value } : {};
    const duree = values.duree_minutes === "" ? null : Number(values.duree_minutes);
    const data = {
      mission: mission.id,
      objet: values.objet,
      date_prevue: fromLocalInput(values.date_prevue),
      etape: values.etape === "" ? null : values.etape,
      auditeurs: values.auditeurs.map(Number),
      interlocuteurs: values.interlocuteurs.map(Number),
      ...(interview || duree !== null ? { duree_minutes: duree } : {}),
      ...optional("lieu", values.lieu),
      ...optional("autres_interlocuteurs", values.autres_interlocuteurs),
      ...optional("themes", values.themes),
      ...optional("compte_rendu", values.compte_rendu),
      ...optional("note_synthese", values.note_synthese),
    };
    try {
      await save.mutateAsync(interview ? { id: interview.id, data } : { data });
      onDone();
    } catch (e) {
      setFormError(
        applyApiErrors(e, setError, [
          "objet",
          "date_prevue",
          "duree_minutes",
          "lieu",
          "etape",
          "autres_interlocuteurs",
          "themes",
          "compte_rendu",
          "note_synthese",
        ]),
      );
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{interview ? t.editInterview : t.planInterview}</DialogTitle>
        <DialogDescription className="sr-only">{mission.reference}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.objectLabel} error={errors.objet?.message}>
        {(p) => <Input {...p} maxLength={300} required {...register("objet")} />}
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={t.dateLabel} error={errors.date_prevue?.message}>
          {(p) => <Input {...p} type="datetime-local" required {...register("date_prevue")} />}
        </FormField>
        <FormField label={t.durationLabel} error={errors.duree_minutes?.message}>
          {(p) => <Input {...p} type="number" inputMode="numeric" {...register("duree_minutes")} />}
        </FormField>
      </div>
      <FormField label={t.placeLabel} error={errors.lieu?.message}>
        {(p) => <Input {...p} maxLength={200} {...register("lieu")} />}
      </FormField>
      <FormField label={t.stepLabel} error={errors.etape?.message}>
        {(p) => (
          <NativeSelect {...p} {...register("etape")}>
            <option value="">{t.noStep}</option>
            {(steps.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.romain} · {s.titre}
              </option>
            ))}
          </NativeSelect>
        )}
      </FormField>
      <Controller
        control={control}
        name="auditeurs"
        render={({ field }) => (
          <AuditorChoice mission={mission} value={field.value} onChange={field.onChange} />
        )}
      />
      <Controller
        control={control}
        name="interlocuteurs"
        render={({ field }) => (
          <UserPicker
            label={t.internalInterlocutors}
            value={field.value}
            onChange={field.onChange}
            known={interview?.interlocuteurs_detail}
          />
        )}
      />
      <FormField label={t.otherInterlocutors} error={errors.autres_interlocuteurs?.message}>
        {(p) => <Textarea {...p} rows={2} {...register("autres_interlocuteurs")} />}
      </FormField>
      <FormField label={t.themesLabel} error={errors.themes?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("themes")} />}
      </FormField>
      <FormField label={t.minutesLabel} error={errors.compte_rendu?.message}>
        {(p) => <Textarea {...p} rows={4} {...register("compte_rendu")} />}
      </FormField>
      <FormField label={t.synthesisLabel} error={errors.note_synthese?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("note_synthese")} />}
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
