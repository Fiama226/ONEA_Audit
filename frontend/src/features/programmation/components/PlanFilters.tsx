import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fr } from "@/i18n/fr";
import { INTERVENTION_TYPE_LABELS, quarterLabel } from "../labels";
import { NativeSelect } from "../shared";
import type { InterventionType } from "../types";

export type PlanFilterValues = { processus: string; type: string; trimestre: string; q: string };

export type ProcessOption = { id: string; code: string; libelle: string };

/** Filtres de la liste des missions prévues (filtrage côté client, reflété dans l'URL). */
export function PlanFilters({
  values,
  processes,
  onChange,
}: {
  values: PlanFilterValues;
  processes: ProcessOption[];
  onChange: (next: Partial<PlanFilterValues>) => void;
}) {
  const c = fr.programmationPlans;
  return (
    <div
      role="group"
      aria-label={c.filtersLabel}
      className="flex flex-wrap items-end gap-4 print:hidden"
    >
      <div className="grid gap-1.5">
        <Label htmlFor="plan-filter-processus">{c.filterProcess}</Label>
        <NativeSelect
          id="plan-filter-processus"
          value={values.processus}
          onChange={(e) => onChange({ processus: e.target.value })}
        >
          <option value="">{c.filterAll}</option>
          {processes.map((p) => (
            <option key={p.id} value={p.id}>
              {p.code} - {p.libelle}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="plan-filter-type">{c.filterType}</Label>
        <NativeSelect
          id="plan-filter-type"
          value={values.type}
          onChange={(e) => onChange({ type: e.target.value })}
        >
          <option value="">{c.filterAll}</option>
          {(Object.keys(INTERVENTION_TYPE_LABELS) as InterventionType[]).map((t) => (
            <option key={t} value={t}>
              {INTERVENTION_TYPE_LABELS[t]}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="plan-filter-trimestre">{c.filterQuarter}</Label>
        <NativeSelect
          id="plan-filter-trimestre"
          value={values.trimestre}
          onChange={(e) => onChange({ trimestre: e.target.value })}
        >
          <option value="">{c.filterAll}</option>
          {[1, 2, 3, 4].map((q) => (
            <option key={q} value={String(q)}>
              {quarterLabel(q)}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="plan-filter-q">{c.filterSearch}</Label>
        <Input
          id="plan-filter-q"
          type="search"
          placeholder={c.filterSearchPlaceholder}
          value={values.q}
          onChange={(e) => onChange({ q: e.target.value })}
        />
      </div>
    </div>
  );
}
