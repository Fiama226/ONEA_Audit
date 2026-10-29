import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useUpdateAuditPlan } from "../api";
import { planEditSchema, type PlanEditValues } from "../schemas/plan";
import { applyApiErrors } from "../shared";
import type { AuditPlan } from "../types";

const FIELDS = ["libelle", "commentaire"] as const;

/** Modification du libellé et du commentaire d'un brouillon (l'année reste fixe). */
export function EditPlanDialog({
  plan,
  open,
  onOpenChange,
}: {
  plan: AuditPlan;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const c = fr.programmationPlans;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{c.editTitle}</DialogTitle>
          <DialogDescription>{c.editDescription}</DialogDescription>
        </DialogHeader>
        <EditPlanForm plan={plan} onOpenChange={onOpenChange} />
      </DialogContent>
    </Dialog>
  );
}

function EditPlanForm({
  plan,
  onOpenChange,
}: {
  plan: AuditPlan;
  onOpenChange: (open: boolean) => void;
}) {
  const c = fr.programmationPlans;
  const update = useUpdateAuditPlan();
  const [general, setGeneral] = useState("");
  const form = useForm<PlanEditValues>({
    resolver: zodResolver(planEditSchema),
    defaultValues: { libelle: plan.libelle, commentaire: plan.commentaire ?? "" },
  });

  async function onSubmit(values: PlanEditValues) {
    setGeneral("");
    try {
      await update.mutateAsync({ id: plan.id, data: values });
      onOpenChange(false);
    } catch (e) {
      setGeneral(applyApiErrors(e, form.setError, FIELDS) ?? "");
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
        <FormField
          control={form.control}
          name="libelle"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{fr.programmation.label}</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="commentaire"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{fr.programmation.comment}</FormLabel>
              <FormControl>
                <Textarea rows={3} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {general && (
          <p role="alert" className="text-sm text-destructive">
            {general}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            {fr.common.cancel}
          </Button>
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? c.saving : fr.common.save}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}
