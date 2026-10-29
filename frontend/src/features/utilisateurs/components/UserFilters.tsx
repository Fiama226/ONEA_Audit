import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/features/referentiel/components/NativeSelect";
import { fr } from "@/i18n/fr";
import { directionLabel, ROLE_LABELS } from "../labels";
import type { Direction, Role } from "../types";

export type UserFilterValues = {
  q: string;
  role: string;
  statut: string;
  direction: string;
  sync: string;
};

const SEARCH_DELAY_MS = 300;
/** Limite du backend : au-delà, la requête est refusée (400). */
export const SEARCH_MAX_LENGTH = 100;
const ROLES = Object.keys(ROLE_LABELS) as Role[];

/** Filtres de la liste ; la recherche n'est transmise qu'après 300 ms d'inactivité. */
export function UserFilters({
  values,
  directions,
  onChange,
}: {
  values: UserFilterValues;
  directions: Direction[];
  onChange: (next: Partial<UserFilterValues>) => void;
}) {
  const t = fr.utilisateurs.liste;
  const [text, setText] = useState(values.q);
  const [syncedQ, setSyncedQ] = useState(values.q);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  });

  // L'URL fait foi : retour/avance du navigateur ou « Effacer les filtres » réinitialisent la saisie.
  if (values.q !== syncedQ) {
    setSyncedQ(values.q);
    setText(values.q);
  }

  useEffect(() => {
    const term = text.trim();
    if (term === values.q) return;
    const timer = setTimeout(() => onChangeRef.current({ q: term }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [text, values.q]);

  return (
    <form
      role="search"
      aria-label={t.filtersLabel}
      onSubmit={(e) => e.preventDefault()}
      className="flex flex-wrap items-end gap-4 print:hidden"
    >
      <div className="grid min-w-64 gap-1.5">
        <Label htmlFor="user-filter-q">{t.search}</Label>
        <Input
          id="user-filter-q"
          type="search"
          maxLength={SEARCH_MAX_LENGTH}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="user-filter-role">{t.role}</Label>
        <NativeSelect
          id="user-filter-role"
          value={values.role}
          onChange={(e) => onChange({ role: e.target.value })}
        >
          <option value="">{t.allRoles}</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="user-filter-statut">{t.status}</Label>
        <NativeSelect
          id="user-filter-statut"
          value={values.statut}
          onChange={(e) => onChange({ statut: e.target.value })}
        >
          <option value="">{t.allStatuses}</option>
          <option value="actif">{t.statusActive}</option>
          <option value="inactif">{t.statusInactive}</option>
          <option value="attente">{t.statusPending}</option>
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="user-filter-direction">{t.direction}</Label>
        <NativeSelect
          id="user-filter-direction"
          value={values.direction}
          onChange={(e) => onChange({ direction: e.target.value })}
        >
          <option value="">{t.allDirections}</option>
          {directions.map((d) => (
            <option key={d.code} value={d.code}>
              {directionLabel(d.code, d.libelle)}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="user-filter-sync">{t.sync}</Label>
        <NativeSelect
          id="user-filter-sync"
          value={values.sync}
          onChange={(e) => onChange({ sync: e.target.value })}
        >
          <option value="">{t.syncAll}</option>
          <option value="ECHEC">{t.syncFailed}</option>
          <option value="EN_ATTENTE">{t.syncPending}</option>
        </NativeSelect>
      </div>
    </form>
  );
}
