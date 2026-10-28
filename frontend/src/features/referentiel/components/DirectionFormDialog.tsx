import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import { useSaveDirection } from "../api";
import { applyApiErrors } from "../formErrors";
import { TYPE_ENTITE_LABELS } from "../labels";
import { directionSchema, type DirectionFormValues } from "../schemas/direction";
import type { Direction } from "../types";
import { ALERT_CLASS, FormField, SELECT_CLASS } from "./FormField";

const s = fr.refStructure;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Entité à modifier ; absent pour une création. */
  direction?: Direction;
  /** Directions pouvant recevoir un département. */
  parents: Direction[];
};

export function DirectionFormDialog({ open, onOpenChange, direction, parents }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DirectionForm direction={direction} parents={parents} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function DirectionForm({
  direction,
  parents,
  onDone,
}: Pick<Props, "direction" | "parents"> & { onDone: () => void }) {
  const save = useSaveDirection();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<DirectionFormValues>({
    resolver: zodResolver(directionSchema),
    defaultValues: {
      code: direction?.code ?? "",
      libelle: direction?.libelle ?? "",
      type: direction?.type ?? "DIRECTION",
      parent: direction?.parent ?? "",
    },
  });
  const type = useWatch({ control, name: "type" });

  async function onSubmit(values: DirectionFormValues) {
    setFormError(null);
    const data = {
      code: values.code,
      libelle: values.libelle,
      type: values.type,
      parent: values.type === "DEPARTEMENT" ? values.parent : null,
    };
    try {
      await save.mutateAsync(direction ? { id: direction.id, data } : { data });
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["code", "libelle", "type", "parent"]));
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{direction ? s.editDirectionTitle : s.createDirectionTitle}</DialogTitle>
        <DialogDescription className="sr-only">{s.addEntity}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={fr.referentiel.type} error={errors.type?.message}>
        {(p) => (
          <select {...p} className={SELECT_CLASS} {...register("type")}>
            {(["DIRECTION", "DEPARTEMENT"] as const).map((t) => (
              <option key={t} value={t}>
                {TYPE_ENTITE_LABELS[t]}
              </option>
            ))}
          </select>
        )}
      </FormField>
      <FormField label={fr.referentiel.code} error={errors.code?.message} help={s.errCodeDirection}>
        {(p) => <Input {...p} autoComplete="off" {...register("code")} />}
      </FormField>
      <FormField label={fr.referentiel.libelle} error={errors.libelle?.message}>
        {(p) => <Input {...p} maxLength={200} {...register("libelle")} />}
      </FormField>
      {type === "DEPARTEMENT" && (
        <FormField label={fr.referentiel.directionRattachement} error={errors.parent?.message}>
          {(p) => (
            <select {...p} className={SELECT_CLASS} {...register("parent")}>
              <option value="">{s.selectParent}</option>
              {parents
                .filter((d) => d.id !== direction?.id)
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.code} - {d.libelle}
                  </option>
                ))}
            </select>
          )}
        </FormField>
      )}
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
