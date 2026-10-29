import { useId, useMemo, useState, type Ref } from "react";
import { Input } from "@/components/ui/input";
import { fr } from "@/i18n/fr";
import type { Direction } from "@/features/referentiel/types";

const s = fr.programmationLignes;

type DeletedEntity = { id: string; code: string; libelle: string };

type Props = {
  directions: Direction[];
  /** Entités déjà citées par la mission mais supprimées du référentiel : décochables, jamais ajoutables. */
  deleted?: DeletedEntity[];
  value: string[];
  onChange: (next: string[]) => void;
  /** Reçoit le focus quand une erreur serveur est posée sur le champ. */
  searchRef?: Ref<HTMLInputElement>;
  error?: string;
};

/** Cases à cocher des directions, leurs départements en sous-liste, avec recherche locale. */
export function EntitiesPicker({
  directions,
  deleted = [],
  value,
  onChange,
  searchRef,
  error,
}: Props) {
  const [query, setQuery] = useState("");
  const errorId = useId();

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

  const box = (id: string, label: string) => (
    <label className="flex min-h-9 items-center gap-2 text-sm">
      <input
        type="checkbox"
        className="size-4 accent-primary"
        checked={value.includes(id)}
        onChange={(e) => toggle(id, e.target.checked)}
      />
      {label}
    </label>
  );

  const label = (d: Direction) => `${d.code} - ${d.libelle}`;

  return (
    <fieldset className="grid gap-2" aria-describedby={error ? errorId : undefined}>
      <legend className="text-sm font-medium">{s.entitiesLegend}</legend>
      <Input
        ref={searchRef}
        type="search"
        aria-label={s.entitiesSearch}
        placeholder={s.entitiesSearch}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ul className="grid max-h-64 gap-0.5 overflow-y-auto rounded-md border border-border p-2">
        {groups.length === 0 && deleted.length === 0 && (
          <li className="text-sm text-text-muted">{s.entitiesNone}</li>
        )}
        {groups.map(({ root, children }) => (
          <li key={root.id}>
            {box(root.id, label(root))}
            {children.length > 0 && (
              <ul className="ml-6">
                {children.map((c) => (
                  <li key={c.id}>{box(c.id, label(c))}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
        {deleted.map((d) => (
          <li key={d.id}>{box(d.id, `${d.code} - ${d.libelle} ${fr.programmation.deleted}`)}</li>
        ))}
      </ul>
      {error && (
        <p id={errorId} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </fieldset>
  );
}
