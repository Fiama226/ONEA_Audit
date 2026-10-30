import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
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
import { Textarea } from "@/components/ui/textarea";
import { UserPicker } from "@/features/missions/components/UserPicker";
import { fr } from "@/i18n/fr";
import { useSaveAction } from "../api";
import {
  ACTION_FIELDS,
  actionSchema,
  defaultActionValues,
  todayIso,
  toActionPayload,
  type ActionFormValues,
} from "../schemas/action";
import type { ActionCorrective } from "../types";

const t = fr.planActions;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  missionId: string;
  recommandation: { id: string; reference: string; libelle: string };
  /** Action à modifier ; absente : création. */
  action?: ActionCorrective;
};

/** Création ou modification d'une action corrective ; les refus du serveur s'affichent sous les champs. */
export function ActionDialog({ open, onOpenChange, ...rest }: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        {open && <ActionForm {...rest} onClose={() => onOpenChange(false)} />}
      </AlertDialogContent>
    </AlertDialog>
  );
}

function ActionForm({
  missionId,
  recommandation,
  action,
  onClose,
}: Omit<Props, "open" | "onOpenChange"> & { onClose: () => void }) {
  const save = useSaveAction();
  const [formError, setFormError] = useState<string | null>(null);
  const schema = useMemo(() => actionSchema(action?.echeance), [action?.echeance]);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ActionFormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaultActionValues(action),
  });

  async function submit(values: ActionFormValues) {
    setFormError(null);
    const data = toActionPayload(recommandation.id, values);
    try {
      if (action === undefined) {
        await save.mutateAsync({ missionId, data });
      } else {
        const { recommandation: _unchanged, ...changes } = data;
        void _unchanged;
        await save.mutateAsync({ missionId, id: action.id, data: changes });
      }
      onClose();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ACTION_FIELDS));
    }
  }

  const title = action
    ? t.actionDialogTitleEdit.replace("{reference}", action.reference)
    : t.actionDialogTitleNew;

  return (
    <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
      <AlertDialogHeader>
        <AlertDialogTitle>{title}</AlertDialogTitle>
        <AlertDialogDescription>
          {t.actionDialogDescription
            .replace("{reference}", recommandation.reference)
            .replace("{libelle}", recommandation.libelle)}
        </AlertDialogDescription>
      </AlertDialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={t.fieldMeasure} error={errors.libelle?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("libelle")} />}
      </FormField>
      <Controller
        control={control}
        name="responsable"
        render={({ field }) => (
          <UserPicker
            // eslint-disable-next-line jsx-a11y/aria-role -- `role` est ici le rôle métier, pas un rôle ARIA
            role="AUDITE"
            single
            label={t.fieldOwner}
            value={field.value === "" ? [] : [field.value]}
            onChange={(value) => field.onChange(value[0] ?? "")}
            known={action?.responsable_detail ? [action.responsable_detail] : []}
            error={errors.responsable?.message}
          />
        )}
      />
      <FormField label={t.fieldDue} error={errors.echeance?.message}>
        {(p) => <Input {...p} type="date" min={todayIso()} {...register("echeance")} />}
      </FormField>
      <FormField label={t.fieldIndicator} error={errors.indicateur?.message}>
        {(p) => <Input {...p} {...register("indicateur")} />}
      </FormField>
      <FormField label={t.fieldMeans} error={errors.moyens?.message}>
        {(p) => <Textarea {...p} rows={2} {...register("moyens")} />}
      </FormField>
      <AlertDialogFooter>
        <AlertDialogCancel type="button" onClick={onClose}>
          {fr.common.cancel}
        </AlertDialogCancel>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? t.saving : t.save}
        </Button>
      </AlertDialogFooter>
    </form>
  );
}
