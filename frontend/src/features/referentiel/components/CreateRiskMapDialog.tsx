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
import { useCreateRiskMap } from "../api";
import { applyServerErrors } from "../riskServerErrors";
import { defaultRiskMapLibelle, riskMapSchema, type RiskMapFormValues } from "../schemas/riskMap";
import type { CartographieVersion } from "../types";
import { NativeSelect } from "./NativeSelect";

const FIELDS = ["annee", "libelle", "commentaire", "source"] as const;

export function CreateRiskMapDialog({
  open,
  onOpenChange,
  versions,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Versions existantes : seules les validées peuvent servir de source. */
  versions: CartographieVersion[];
}) {
  const c = fr.refCartographie;
  const navigate = useNavigate();
  const create = useCreateRiskMap();
  const [general, setGeneral] = useState("");
  const year = String(new Date().getFullYear());
  const form = useForm<RiskMapFormValues>({
    resolver: zodResolver(riskMapSchema),
    defaultValues: {
      annee: year,
      libelle: defaultRiskMapLibelle(year),
      commentaire: "",
      source: "",
    },
  });
  const sources = versions.filter((v) => v.statut === "VALIDEE");

  async function onSubmit(values: RiskMapFormValues) {
    setGeneral("");
    try {
      const created = await create.mutateAsync({
        annee: Number(values.annee),
        libelle: values.libelle,
        commentaire: values.commentaire || undefined,
        source: values.source || undefined,
      });
      onOpenChange(false);
      void navigate(`/referentiel/cartographies/${created.id}`);
    } catch (e) {
      setGeneral(applyServerErrors(e, form.setError, FIELDS));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{c.createTitle}</DialogTitle>
          <DialogDescription>{c.createDescription}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="annee"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldAnnee}</FormLabel>
                  <FormControl>
                    <Input
                      inputMode="numeric"
                      {...field}
                      onChange={(e) => {
                        const previous = defaultRiskMapLibelle(field.value);
                        field.onChange(e);
                        if (form.getValues("libelle") === previous) {
                          form.setValue("libelle", defaultRiskMapLibelle(e.target.value));
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
              name="source"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{c.fieldSource}</FormLabel>
                  <FormControl>
                    <NativeSelect {...field}>
                      <option value="">{c.sourceNone}</option>
                      {sources.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.libelle}
                        </option>
                      ))}
                    </NativeSelect>
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
      </DialogContent>
    </Dialog>
  );
}
