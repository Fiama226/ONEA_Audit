import { fr } from "@/i18n/fr";
import { yearOptions } from "../year";

/** Sélecteur d'année : une seule ligne de filtres en tête des tableaux de bord. */
export function YearFilter({
  value,
  onChange,
}: {
  value: number;
  onChange: (annee: number) => void;
}) {
  const years = yearOptions();
  if (!years.includes(value)) years.push(value);
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3 print:hidden">
      <label htmlFor="dashboard-year" className="text-sm font-medium">
        {fr.tableauxDirection.yearLabel}
      </label>
      <select
        id="dashboard-year"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-9 rounded-md border border-border bg-surface px-3 text-sm"
      >
        {years
          .sort((a, b) => b - a)
          .map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
      </select>
    </div>
  );
}
