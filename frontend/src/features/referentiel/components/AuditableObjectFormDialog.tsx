import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
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
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useSaveAuditableObject } from "../api";
import { applyApiErrors } from "@/api/formErrors";
import { auditableObjectSchema, type AuditableObjectFormValues } from "../schemas/auditableObject";
import type { NatureObjet } from "../types";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";

const s = fr.refStructure;

export type AuditableObjectTarget = {
  processId: string;
  nature: NatureObjet;
  /** Domaine parent d'une opération. */
  parentId?: string;
  /** Élément à modifier ; absent pour une création. */
  existing?: { id: string; libelle: string; description?: string; ordre?: number };
};

type Props = {
  target: AuditableObjectTarget | null;
  onOpenChange: (open: boolean) => void;
};

export function AuditableObjectFormDialog({ target, onOpenChange }: Props) {
  return (
    <Dialog open={target !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        {target && <ObjectForm target={target} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function ObjectForm({ target, onDone }: { target: AuditableObjectTarget; onDone: () => void }) {
  const save = useSaveAuditableObject();
  const [formError, setFormError] = useState<string | null>(null);
  const { existing, nature } = target;
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<AuditableObjectFormValues>({
    resolver: zodResolver(auditableObjectSchema),
    defaultValues: {
      libelle: existing?.libelle ?? "",
      description: existing?.description ?? "",
      ordre: existing?.ordre ?? 0,
    },
  });

  async function onSubmit(values: AuditableObjectFormValues) {
    setFormError(null);
    try {
      await save.mutateAsync(
        existing
          ? { id: existing.id, data: values }
          : {
              data: {
                ...values,
                processus: target.processId,
                nature,
                parent: nature === "OPERATION" ? (target.parentId ?? null) : null,
              },
            },
      );
      onDone();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["libelle", "description", "ordre"]));
    }
  }

  const title =
    nature === "DOMAINE"
      ? existing
        ? s.editDomainTitle
        : s.newDomainTitle
      : existing
        ? s.editOperationTitle
        : s.newOperationTitle;

  return (
    <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription className="sr-only">{title}</DialogDescription>
      </DialogHeader>
      {formError && (
        <p role="alert" className={ALERT_CLASS}>
          {formError}
        </p>
      )}
      <FormField label={fr.referentiel.libelle} error={errors.libelle?.message}>
        {(p) => <Input {...p} maxLength={200} {...register("libelle")} />}
      </FormField>
      <FormField label={s.description} error={errors.description?.message}>
        {(p) => <Textarea {...p} rows={3} {...register("description")} />}
      </FormField>
      <FormField label={fr.referentiel.ordre} error={errors.ordre?.message}>
        {(p) => (
          <Input
            {...p}
            type="number"
            min={0}
            step={1}
            {...register("ordre", { valueAsNumber: true })}
          />
        )}
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
