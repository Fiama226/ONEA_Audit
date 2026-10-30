import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { useTransmitDraft } from "../api";
import { deadlineIso } from "../draftQueries";

const t = fr.rapportProvisoire;
const FIELDS = ["delai_jours"] as const;

const schema = z.object({
  delai_jours: z
    .string()
    .trim()
    .regex(/^\d+$/, t.delayInvalid)
    .refine((v) => Number(v) >= 1 && Number(v) <= 60, t.delayInvalid),
});
type Values = z.infer<typeof schema>;

type Props = { rapportId: string; missionId: string };

/** Transmission du rapport provisoire : délai en jours (15 par défaut) et date limite calculée. */
export function TransmitDraftDialog({ rapportId, missionId }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button type="button" onClick={() => setOpen(true)}>
        {t.transmit}
      </Button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          {open && (
            <TransmitForm
              rapportId={rapportId}
              missionId={missionId}
              onClose={() => setOpen(false)}
            />
          )}
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function TransmitForm({ rapportId, missionId, onClose }: Props & { onClose: () => void }) {
  const transmit = useTransmitDraft();
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { delai_jours: "15" } });
  const delay = useWatch({ control, name: "delai_jours" });
  const days = Number(delay);
  const validDelay = /^\d+$/.test(delay.trim()) && days >= 1 && days <= 60;

  async function submit(values: Values) {
    setFormError(null);
    try {
      await transmit.mutateAsync({
        id: rapportId,
        missionId,
        delaiJours: Number(values.delai_jours),
      });
      setDone(true);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELDS));
    }
  }

  if (done) {
    return (
      <>
        <AlertDialogHeader>
          <AlertDialogTitle>{t.transmitTitle}</AlertDialogTitle>
          <AlertDialogDescription role="status">{t.transmitDone}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose}>{fr.common.close}</AlertDialogCancel>
        </AlertDialogFooter>
      </>
    );
  }

  return (
    <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
      <AlertDialogHeader>
        <AlertDialogTitle>{t.transmitTitle}</AlertDialogTitle>
        <AlertDialogDescription>{t.transmitHelp}</AlertDialogDescription>
      </AlertDialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.delayLabel} help={t.delayHelp} error={errors.delai_jours?.message}>
        {(p) => <Input {...p} type="number" inputMode="numeric" {...register("delai_jours")} />}
      </FormField>
      {validDelay && (
        <p className="text-sm font-medium" role="status">
          {t.deadlinePreview.replace("{date}", formatDate(deadlineIso(days)))}
        </p>
      )}
      <AlertDialogFooter>
        <AlertDialogCancel type="button" onClick={onClose}>
          {fr.common.cancel}
        </AlertDialogCancel>
        <Button type="submit" disabled={transmit.isPending}>
          {transmit.isPending ? t.transmitPending : t.transmitSubmit}
        </Button>
      </AlertDialogFooter>
    </form>
  );
}
