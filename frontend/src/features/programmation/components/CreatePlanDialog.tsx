import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
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
import { useCreateAuditPlan } from "../api";
import { defaultPlanLabel, planSchema, type PlanFormValues } from "../schemas/plan";
import { applyApiErrors } from "../shared";

const FIELDS = ["annee", "libelle", "commentaire"] as const;

/** Le formulaire n'est monté que boîte ouverte : valeurs et erreurs repartent à zéro. */
export function CreatePlanDialog({
  open,
  onOpenChange,
  existingYears,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Années ayant déjà un programme : si l'année en cours en a un, la suivante est proposée. */
  existingYears: number[];
}) {
  const c = fr.programmationPlans;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{c.createTitle}</DialogTitle>
          <DialogDescription>{c.createDescription}</DialogDescription>
        </DialogHeader>
        <CreatePlanForm onOpenChange={onOpenChange} existingYears={existingYears} />
      </DialogContent>
    </Dialog>
  );
}

function CreatePlanForm({
  onOpenChange,
  existingYears,
}: {
  onOpenChange: (open: boolean) => void;
  existingYears: number[];
}) {
  const c = fr.programmationPlans;
  const navigate = useNavigate();
  const create = useCreateAuditPlan();
  const [general, setGeneral] = useState("");
  const current = new Date().getFullYear();
  const year = String(existingYears.includes(current) ? current + 1 : current);
  const form = useForm<PlanFormValues>({
    resolver: zodResolver(planSchema),
    defaultValues: { annee: year, libelle: defaultPlanLabel(year), commentaire: "" },
  });

  async function onSubmit(values: PlanFormValues) {
    setGeneral("");
    try {
      const created = await create.mutateAsync({
        annee: Number(values.annee),
        libelle: values.libelle,
        commentaire: values.commentaire || undefined,
      });
      onOpenChange(false);
      void navigate(`/programme-annuel/${created.id}`);
    } catch (e) {
      setGeneral(applyApiErrors(e, form.setError, FIELDS) ?? "");
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
        <FormField
          control={form.control}
          name="annee"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{fr.programmation.year}</FormLabel>
              <FormControl>
                <Input
                  inputMode="numeric"
                  {...field}
                  onChange={(e) => {
                    const previous = defaultPlanLabel(field.value);
                    field.onChange(e);
                    if (form.getValues("libelle") === previous) {
                      form.setValue("libelle", defaultPlanLabel(e.target.value));
                    }
                  }}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
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
                <Textarea rows={2} {...field} />
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
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? c.creating : fr.common.create}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}
