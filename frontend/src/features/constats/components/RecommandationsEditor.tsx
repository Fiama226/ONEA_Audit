import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { Controller, useFieldArray, type Control, type UseFormRegister } from "react-hook-form";
import { FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { PRIORITE_LABELS } from "../labels";
import type { ConstatFormValues } from "../schemas/constat";
import type { PrioriteRecommandation } from "../types";

const t = fr.constatsUi;
const PRIORITES = Object.keys(PRIORITE_LABELS) as PrioriteRecommandation[];

type Props = {
  control: Control<ConstatFormValues>;
  register: UseFormRegister<ConstatFormValues>;
  editable: boolean;
};

/** Recommandations ordonnées : l'ordre est la position dans la liste (remplacement complet au PATCH). */
export function RecommandationsEditor({ control, register, editable }: Props) {
  const { fields, append, remove, move } = useFieldArray({ control, name: "recommandations" });
  return (
    <section aria-labelledby="constat-recos" className="grid gap-3">
      <h3 id="constat-recos" className="text-base font-semibold">
        {t.recosTitle}
      </h3>
      {fields.length === 0 && <p className="text-sm text-text-muted">{t.noReco}</p>}
      {fields.map((field, index) => {
        const n = String(index + 1);
        return (
          <div
            key={field.id}
            className="grid gap-2 rounded-md border border-border p-3 md:grid-cols-[1fr_12rem_auto]"
          >
            <FormField label={t.recoLabel.replace("{n}", n)}>
              {(p) => (
                <Textarea {...p} rows={2} {...register(`recommandations.${index}.libelle`)} />
              )}
            </FormField>
            <Controller
              control={control}
              name={`recommandations.${index}.priorite`}
              render={({ field: f }) => (
                <FormField label={t.recoPriority.replace("{n}", n)}>
                  {(p) => (
                    <NativeSelect
                      {...p}
                      name={f.name}
                      ref={f.ref}
                      value={f.value}
                      onBlur={f.onBlur}
                      onChange={(e) => f.onChange(e.target.value)}
                    >
                      {PRIORITES.map((k) => (
                        <option key={k} value={k}>
                          {PRIORITE_LABELS[k]}
                        </option>
                      ))}
                    </NativeSelect>
                  )}
                </FormField>
              )}
            />
            {editable && (
              <div className="flex items-end gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t.recoUp.replace("{n}", n)}
                  disabled={index === 0}
                  onClick={() => move(index, index - 1)}
                >
                  <ArrowUp aria-hidden />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t.recoDown.replace("{n}", n)}
                  disabled={index === fields.length - 1}
                  onClick={() => move(index, index + 1)}
                >
                  <ArrowDown aria-hidden />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t.recoRemove.replace("{n}", n)}
                  onClick={() => remove(index)}
                >
                  <Trash2 aria-hidden />
                </Button>
              </div>
            )}
          </div>
        );
      })}
      {editable && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="justify-self-start"
          onClick={() => append({ libelle: "", priorite: "MOYENNE" })}
        >
          <Plus aria-hidden />
          {t.recoAdd}
        </Button>
      )}
    </section>
  );
}
