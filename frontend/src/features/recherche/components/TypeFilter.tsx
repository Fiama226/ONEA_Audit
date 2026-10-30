import { Checkbox } from "@/components/ui/checkbox";
import { fr } from "@/i18n/fr";
import type { TypeResultat } from "../api";

export const SEARCH_TYPES: readonly TypeResultat[] = [
  "MISSION",
  "CONSTAT",
  "RECOMMANDATION",
  "ACTION",
  "DOCUMENT",
];

/** Filtre par type de résultat : groupe de cases à cocher ; aucune case cochée = tous les types. */
export function TypeFilter({
  value,
  onChange,
}: {
  value: readonly TypeResultat[];
  onChange: (next: TypeResultat[]) => void;
}) {
  const toggle = (type: TypeResultat, checked: boolean) =>
    onChange(SEARCH_TYPES.filter((t) => (t === type ? checked : value.includes(t))));
  return (
    <fieldset className="flex flex-wrap items-center gap-x-5 gap-y-2">
      <legend className="sr-only">{fr.rechercheNotifications.searchTypeFilterLabel}</legend>
      {SEARCH_TYPES.map((type) => {
        const id = `search-type-${type}`;
        return (
          <div key={type} className="flex items-center gap-2">
            <Checkbox
              id={id}
              checked={value.includes(type)}
              onCheckedChange={(c) => toggle(type, c === true)}
            />
            <label htmlFor={id} className="text-sm">
              {fr.suivi[`search${type}` as const]}
            </label>
          </div>
        );
      })}
    </fieldset>
  );
}
