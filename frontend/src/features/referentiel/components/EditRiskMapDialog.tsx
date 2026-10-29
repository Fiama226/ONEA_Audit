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
import { useUpdateRiskMap } from "../api";
import { applyApiErrors } from "@/api/formErrors";
import { riskMapEditSchema, type RiskMapEditValues } from "../schemas/riskMap";
import type { CartographieVersion } from "../types";

const FIELDS = ["libelle", "commentaire"] as const;

/** Modification du libellé et du commentaire d'un brouillon (l'année et la source restent fixes). */
export function EditRiskMapDialog({
  version,
  open,
  onOpenChange,
}: {
  version: CartographieVersion;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const c = fr.refCartographie;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{c.editTitle}</DialogTitle>
          <DialogDescription>{c.editDescription}</DialogDescription>
        </DialogHeader>
        <EditRiskMapForm version={version} onOpenChange={onOpenChange} />
      </DialogContent>
    </Dialog>
  );
}

function EditRiskMapForm({
  version,
  onOpenChange,
}: {
  version: CartographieVersion;
  onOpenChange: (open: boolean) => void;
}) {
  const c = fr.refCartographie;
  const update = useUpdateRiskMap();
  const [general, setGeneral] = useState("");
  const form = useForm<RiskMapEditValues>({
    resolver: zodResolver(riskMapEditSchema),
    defaultValues: { libelle: version.libelle, commentaire: version.commentaire ?? "" },
  });

  async function onSubmit(values: RiskMapEditValues) {
    setGeneral("");
    try {
      await update.mutateAsync({ id: version.id, data: values });
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
              <FormLabel>{c.fieldLibelle}</FormLabel>
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
              <FormLabel>{c.fieldCommentaire}</FormLabel>
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
