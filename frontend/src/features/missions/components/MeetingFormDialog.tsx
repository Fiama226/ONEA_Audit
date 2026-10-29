import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
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
import { useSaveMeeting } from "../api";
import { TYPE_REUNION_LABELS } from "../labels";
import { fromLocalInput, toLocalInput } from "../schemas/datetime";
import { meetingSchema, type MeetingFormValues } from "../schemas/meeting";
import type { Mission, Reunion, TypeReunion } from "../types";
import { UserPicker } from "./UserPicker";

const t = fr.missionTravaux;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mission: Mission;
  type: TypeReunion;
  /** Réunion à modifier ; absente pour une planification. */
  meeting?: Reunion;
};

export function MeetingFormDialog({ open, onOpenChange, ...rest }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <MeetingForm {...rest} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function MeetingForm({
  mission,
  type,
  meeting,
  onDone,
}: Omit<Props, "open" | "onOpenChange"> & { onDone: () => void }) {
  const save = useSaveMeeting();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<MeetingFormValues>({
    resolver: zodResolver(meetingSchema),
    defaultValues: {
      date: meeting ? toLocalInput(meeting.date) : "",
      lieu: meeting?.lieu ?? "",
      ordre_du_jour: meeting?.ordre_du_jour ?? "",
      participants: (meeting?.participants ?? []).map(String),
      participants_externes: meeting?.participants_externes ?? "",
      decisions: meeting?.decisions ?? "",
      compte_rendu: meeting?.compte_rendu ?? "",
    },
  });

  async function onSubmit(values: MeetingFormValues) {
    setFormError(null);
    // À la création, les champs texte vides sont omis ; à la modification, ils sont envoyés
    // pour permettre d'effacer une valeur.
    const optional = (key: string, value: string) =>
      meeting || value.trim() !== "" ? { [key]: value } : {};
    const data = {
      mission: mission.id,
      type,
      date: fromLocalInput(values.date),
      participants: values.participants.map(Number),
      ...optional("lieu", values.lieu),
      ...optional("ordre_du_jour", values.ordre_du_jour),
      ...optional("participants_externes", values.participants_externes),
      ...optional("decisions", values.decisions),
      ...optional("compte_rendu", values.compte_rendu),
    };
    try {
      await save.mutateAsync(meeting ? { id: meeting.id, data } : { data });
      onDone();
    } catch (e) {
      setFormError(
        applyApiErrors(e, setError, [
          "date",
          "lieu",
          "ordre_du_jour",
          "participants",
          "participants_externes",
          "decisions",
          "compte_rendu",
        ]),
      );
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t.meetingFormTitle.replace("{type}", TYPE_REUNION_LABELS[type])}</DialogTitle>
        <DialogDescription className="sr-only">{mission.reference}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.dateLabel} error={errors.date?.message}>
        {(p) => <Input {...p} type="datetime-local" required {...register("date")} />}
      </FormField>
      <FormField label={t.placeLabel} error={errors.lieu?.message}>
        {(p) => <Input {...p} maxLength={200} {...register("lieu")} />}
      </FormField>
      <FormField label={t.agendaLabel} error={errors.ordre_du_jour?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("ordre_du_jour")} />}
      </FormField>
      <Controller
        control={control}
        name="participants"
        render={({ field }) => (
          <UserPicker
            label={t.internalParticipants}
            value={field.value}
            onChange={field.onChange}
          />
        )}
      />
      <FormField
        label={t.externalParticipants}
        help={t.externalHelp}
        error={errors.participants_externes?.message}
      >
        {(p) => <Textarea {...p} rows={3} {...register("participants_externes")} />}
      </FormField>
      <FormField label={t.decisionsLabel} error={errors.decisions?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("decisions")} />}
      </FormField>
      <FormField label={t.minutesLabel} error={errors.compte_rendu?.message}>
        {(p) => <Textarea {...p} rows={4} {...register("compte_rendu")} />}
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
