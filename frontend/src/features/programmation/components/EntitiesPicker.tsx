import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import type { Direction } from "@/features/referentiel/types";

const s = fr.programmationLignes;

type Props = {
  directions: Direction[];
  value: string[];
  onChange: (next: string[]) => void;
};

/** Cases à cocher des directions, leurs départements en retrait, avec recherche locale. */
export function EntitiesPicker({ directions, value, onChange }: Props) {
  const [query, setQuery] = useState("");

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matches = (d: Direction) =>
      q === "" || `${d.code} ${d.libelle}`.toLowerCase().includes(q);
    const ids = new Set(directions.map((d) => d.id));
    // Un département dont la direction est absente de la liste est affiché au premier niveau.
    const roots = directions.filter((d) => d.parent == null || !ids.has(d.parent));
    return roots
      .map((root) => {
        const children = directions.filter((d) => d.parent === root.id);
        const shown = matches(root) ? children : children.filter(matches);
        return { root, children: shown, visible: matches(root) || shown.length > 0 };
      })
      .filter((g) => g.visible);
  }, [directions, query]);

  const toggle = (id: string, checked: boolean) =>
    onChange(checked ? [...value, id] : value.filter((v) => v !== id));

  const box = (d: Direction, indent: boolean) => (
    <li key={d.id} className={indent ? "ml-6" : undefined}>
      <label className="flex min-h-9 items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-4 accent-primary"
          checked={value.includes(d.id)}
          onChange={(e) => toggle(d.id, e.target.checked)}
        />
        {d.code} - {d.libelle}
      </label>
    </li>
  );

  return (
    <fieldset className="grid gap-2">
      <legend className="text-sm font-medium">{s.entitiesLegend}</legend>
      <Input
        type="search"
        aria-label={s.entitiesSearch}
        placeholder={s.entitiesSearch}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ul className="grid max-h-64 gap-0.5 overflow-y-auto rounded-md border border-border p-2">
        {groups.length === 0 && <li className="text-sm text-text-muted">{s.entitiesNone}</li>}
        {groups.map(({ root, children }) => (
          <li key={root.id}>
            <ul>
              {box(root, false)}
              {children.map((c) => box(c, true))}
            </ul>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}
