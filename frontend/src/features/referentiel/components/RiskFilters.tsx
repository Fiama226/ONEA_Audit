import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fr } from "@/i18n/fr";
import { NIVEAU_LABELS } from "../labels";
import type { NiveauRisque, Processus } from "../types";
import { NativeSelect } from "@/components/form/NativeSelect";

export type RiskFilterValues = { processus: string; niveau: string; q: string };

export function RiskFilters({
  values,
  processes,
  onChange,
}: {
  values: RiskFilterValues;
  processes: Processus[];
  onChange: (next: Partial<RiskFilterValues>) => void;
}) {
  const c = fr.refCartographie;
  return (
    <div className="flex flex-wrap items-end gap-4 print:hidden">
      <div className="grid gap-1.5">
        <Label htmlFor="filter-processus">{c.filterProcessus}</Label>
        <NativeSelect
          id="filter-processus"
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
        <Label htmlFor="filter-niveau">{c.filterNiveau}</Label>
        <NativeSelect
          id="filter-niveau"
          value={values.niveau}
          onChange={(e) => onChange({ niveau: e.target.value })}
        >
          <option value="">{c.filterAll}</option>
          {(Object.keys(NIVEAU_LABELS) as NiveauRisque[]).map((n) => (
            <option key={n} value={n}>
              {NIVEAU_LABELS[n]}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="filter-q">{c.filterSearch}</Label>
        <Input
          id="filter-q"
          type="search"
          placeholder={c.filterSearchPlaceholder}
          value={values.q}
          onChange={(e) => onChange({ q: e.target.value })}
        />
      </div>
    </div>
  );
}
