import { Plus, Trash2 } from "lucide-react";
import { useFieldArray, type Control, type UseFormRegister } from "react-hook-form";
import { FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { CATEGORIE_CAUSE_LABELS } from "../labels";
import type { ConstatFormValues } from "../schemas/constat";
import type { CategorieCause } from "../types";

const t = fr.constatsUi;
const CATEGORIES = Object.keys(CATEGORIE_CAUSE_LABELS) as CategorieCause[];

type Props = {
  control: Control<ConstatFormValues>;
  register: UseFormRegister<ConstatFormValues>;
  editable: boolean;
};

/** Causes groupées selon les sept rubriques 7M (Ishikawa en champs, sans diagramme dessiné). */
export function CausesEditor({ control, register, editable }: Props) {
  const { fields, append, remove } = useFieldArray({ control, name: "causes" });
  return (
    <section aria-labelledby="constat-causes" className="grid gap-3">
      <div>
        <h3 id="constat-causes" className="text-base font-semibold">
          {t.causesTitle}
        </h3>
        <p className="text-sm text-text-muted">{t.causesHelp}</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {CATEGORIES.map((categorie) => {
          const label = CATEGORIE_CAUSE_LABELS[categorie];
          const rows = fields
            .map((field, index) => ({ field, index }))
            .filter(({ field }) => field.categorie === categorie);
          return (
            <fieldset
              key={categorie}
              className="grid content-start gap-2 rounded-md border border-border p-3"
            >
              <legend className="px-1 text-sm font-medium">{label}</legend>
              {rows.map(({ field, index }, n) => (
                <div key={field.id} className="flex items-start gap-2">
                  <div className="grow">
                    <FormField
                      label={t.causeLabel
                        .replace("{categorie}", label)
                        .replace("{n}", String(n + 1))}
                    >
                      {(p) => (
                        <Textarea {...p} rows={2} {...register(`causes.${index}.description`)} />
                      )}
                    </FormField>
                  </div>
                  {editable && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="mt-6"
                      aria-label={t.causeRemove
                        .replace("{categorie}", label)
                        .replace("{n}", String(n + 1))}
                      onClick={() => remove(index)}
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  )}
                </div>
              ))}
              {editable && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="justify-self-start"
                  onClick={() => append({ categorie, description: "" })}
                >
                  <Plus aria-hidden />
                  {t.causeAdd.replace("{categorie}", label)}
                </Button>
              )}
            </fieldset>
          );
        })}
      </div>
    </section>
  );
}
