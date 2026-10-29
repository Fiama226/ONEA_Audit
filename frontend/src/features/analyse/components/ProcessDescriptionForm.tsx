import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Mission } from "@/features/missions/types";
import { fr } from "@/i18n/fr";
import { useSaveProcessDescription } from "../api";
import { CATEGORIE_OBJECTIF_LABELS, TYPOLOGIE_PROCESSUS_LABELS } from "../labels";
import {
  processDescriptionSchema,
  type ProcessDescriptionFormValues,
} from "../schemas/processDescription";
import type { CategorieObjectif, DescriptionProcessus, TypologieProcessus } from "../types";

const t = fr.analyseIII;

type Props = {
  mission: Mission;
  processus: Mission["processus_detail"][number];
  description?: DescriptionProcessus;
  editable: boolean;
};

const TEXT_FIELDS = [
  ["description", t.narrative, 5],
  ["objectifs", t.objectives, 3],
  ["indicateurs", t.indicators, 3],
  ["sources", t.sources, 3],
  ["references_diagrammes", t.diagramRefs, 2],
] as const;

const FIELD_NAMES = [
  "typologie",
  "categories_objectifs",
  ...TEXT_FIELDS.map(([name]) => name),
] as const;

export function ProcessDescriptionForm({ mission, processus, description, editable }: Props) {
  const save = useSaveProcessDescription();
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const writable = editable && !description?.etape_close;
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ProcessDescriptionFormValues>({
    resolver: zodResolver(processDescriptionSchema),
    defaultValues: {
      typologie: description?.typologie ?? "",
      categories_objectifs: description?.categories_objectifs ?? [],
      description: description?.description ?? "",
      objectifs: description?.objectifs ?? "",
      indicateurs: description?.indicateurs ?? "",
      sources: description?.sources ?? "",
      references_diagrammes: description?.references_diagrammes ?? "",
    },
  });

  async function onSubmit(values: ProcessDescriptionFormValues) {
    setFormError(null);
    setSaved(false);
    try {
      // Le serveur fait un upsert (mission, processus) : toujours un POST.
      await save.mutateAsync({ data: { mission: mission.id, processus: processus.id, ...values } });
      setSaved(true);
    } catch (e) {
      setFormError(applyApiErrors(e, setError, FIELD_NAMES));
    }
  }

  const title = `${processus.code} — ${processus.libelle}`;
  const badge = (
    <Badge variant={description ? "secondary" : "outline"}>
      {description ? t.described : t.toDescribe}
    </Badge>
  );

  if (!writable) {
    return (
      <article className="grid gap-2 rounded-md border border-border p-4" aria-label={title}>
        <header className="flex flex-wrap items-center gap-2">
          <h5 className="text-sm font-semibold">{title}</h5>
          {badge}
        </header>
        <dl className="grid gap-2 text-sm">
          <ReadRow label={t.typology}>
            {description?.typologie
              ? TYPOLOGIE_PROCESSUS_LABELS[description.typologie as TypologieProcessus]
              : ""}
          </ReadRow>
          <ReadRow label={t.objectiveCategories}>
            {(description?.categories_objectifs ?? [])
              .map((c) => CATEGORIE_OBJECTIF_LABELS[c])
              .join(", ")}
          </ReadRow>
          {TEXT_FIELDS.map(([name, label]) => (
            <ReadRow key={name} label={label}>
              {description?.[name] ?? ""}
            </ReadRow>
          ))}
        </dl>
      </article>
    );
  }

  return (
    <article className="rounded-md border border-border p-4" aria-label={title}>
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h5 className="text-sm font-semibold">{title}</h5>
        {badge}
      </header>
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="grid gap-3" noValidate>
        <FormField label={t.typology} error={errors.typologie?.message}>
          {(p) => (
            <Controller
              control={control}
              name="typologie"
              render={({ field }) => (
                <NativeSelect {...p} {...field} className="sm:max-w-xs">
                  <option value="">{t.noTypology}</option>
                  {(Object.keys(TYPOLOGIE_PROCESSUS_LABELS) as TypologieProcessus[]).map((k) => (
                    <option key={k} value={k}>
                      {TYPOLOGIE_PROCESSUS_LABELS[k]}
                    </option>
                  ))}
                </NativeSelect>
              )}
            />
          )}
        </FormField>
        <fieldset
          className="grid gap-2"
          aria-describedby={errors.categories_objectifs ? `${processus.id}-cat-err` : undefined}
        >
          <legend className="text-sm font-medium">{t.objectiveCategories}</legend>
          <Controller
            control={control}
            name="categories_objectifs"
            render={({ field }) => (
              <div className="flex flex-wrap gap-4">
                {(Object.keys(CATEGORIE_OBJECTIF_LABELS) as CategorieObjectif[]).map((c) => {
                  const id = `${processus.id}-cat-${c}`;
                  return (
                    <div key={c} className="flex items-center gap-2">
                      <Checkbox
                        id={id}
                        checked={field.value.includes(c)}
                        onCheckedChange={(on) =>
                          field.onChange(
                            on === true ? [...field.value, c] : field.value.filter((v) => v !== c),
                          )
                        }
                      />
                      <Label htmlFor={id}>{CATEGORIE_OBJECTIF_LABELS[c]}</Label>
                    </div>
                  );
                })}
              </div>
            )}
          />
          {errors.categories_objectifs && (
            <p id={`${processus.id}-cat-err`} className="text-sm text-destructive">
              {errors.categories_objectifs.message}
            </p>
          )}
        </fieldset>
        {TEXT_FIELDS.map(([name, label, rows]) => (
          <FormField
            key={name}
            label={label}
            error={errors[name]?.message}
            help={name === "indicateurs" ? t.indicatorsHelp : undefined}
          >
            {(p) => <Textarea {...p} {...register(name)} rows={rows} maxLength={10500} />}
          </FormField>
        ))}
        {formError && (
          <p role="alert" className="text-sm text-destructive">
            {formError}
          </p>
        )}
        {saved && (
          <p role="status" className="text-sm text-text-muted">
            {t.savedDescription}
          </p>
        )}
        <div className="print:hidden">
          <Button type="submit" disabled={save.isPending}>
            {t.saveDescription}
          </Button>
        </div>
      </form>
    </article>
  );
}

function ReadRow({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <dt className="font-medium">{label}</dt>
      <dd className="whitespace-pre-wrap">{children || t.empty}</dd>
    </div>
  );
}
