import { useId } from "react";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Role } from "@/auth/types";
import { useMissions } from "@/features/missions/api";
import { useDirections } from "@/features/referentiel/api";
import { fr } from "@/i18n/fr";
import {
  PRIORITE_LABELS,
  STATUT_RECOMMANDATION_SUIVI_LABELS,
  STATUT_SUIVI_LABELS,
} from "../labels";

const t = fr.suiviRegistre;

export type RegisterView = "recommandations" | "actions";

/** Valeurs des filtres, telles que conservées dans l'URL (textes). */
export type FilterValues = {
  annee: string;
  mission: string;
  entite: string;
  priorite: string;
  statut: string;
  en_retard: boolean;
  mine: boolean;
};

export const EMPTY_FILTERS: FilterValues = {
  annee: "",
  mission: "",
  entite: "",
  priorite: "",
  statut: "",
  en_retard: false,
  mine: false,
};

type Props = {
  view: RegisterView;
  role: Role;
  values: FilterValues;
  onChange: (patch: Partial<FilterValues>) => void;
  onReset: () => void;
};

function Field({ label, children }: { label: string; children: (id: string) => React.ReactNode }) {
  const id = useId();
  return (
    <div className="grid gap-1">
      <Label htmlFor={id} className="text-xs text-text-muted">
        {label}
      </Label>
      {children(id)}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  const id = useId();
  return (
    <div className="flex items-center gap-2 pb-2">
      <Checkbox id={id} checked={checked} onCheckedChange={(v) => onChange(v === true)} />
      <Label htmlFor={id} className="font-normal">
        {label}
      </Label>
    </div>
  );
}

/** Filtres du registre sur une ligne ; l'état est tenu par la page (paramètres d'URL). */
export function RegisterFilters({ view, role, values, onChange, onReset }: Props) {
  const missions = useMissions({ page_size: 100 });
  const directions = useDirections({ page_size: 100 });
  const statusLabels =
    view === "actions" ? STATUT_SUIVI_LABELS : STATUT_RECOMMANDATION_SUIVI_LABELS;

  return (
    <form
      role="search"
      aria-label={t.filtersLabel}
      onSubmit={(e) => e.preventDefault()}
      className="flex flex-wrap items-end gap-3 print:hidden"
    >
      <Field label={t.filterYear}>
        {(id) => (
          <Input
            id={id}
            type="number"
            inputMode="numeric"
            min={2000}
            max={2100}
            className="w-24"
            value={values.annee}
            onChange={(e) => onChange({ annee: e.target.value })}
          />
        )}
      </Field>
      <Field label={t.filterMission}>
        {(id) => (
          <NativeSelect
            id={id}
            className="w-56"
            value={values.mission}
            onChange={(e) => onChange({ mission: e.target.value })}
          >
            <option value="">{t.filterAll}</option>
            {(missions.data?.results ?? []).map((m) => (
              <option key={m.id} value={m.id}>
                {m.reference} · {m.titre}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
      <Field label={t.filterEntity}>
        {(id) => (
          <NativeSelect
            id={id}
            className="w-44"
            value={values.entite}
            onChange={(e) => onChange({ entite: e.target.value })}
          >
            <option value="">{t.filterAll}</option>
            {(directions.data?.results ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.code} · {d.libelle}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
      {view === "recommandations" && (
        <Field label={t.filterPriority}>
          {(id) => (
            <NativeSelect
              id={id}
              className="w-32"
              value={values.priorite}
              onChange={(e) => onChange({ priorite: e.target.value })}
            >
              <option value="">{t.filterAll}</option>
              {Object.entries(PRIORITE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      )}
      <Field label={t.filterStatus}>
        {(id) => (
          <NativeSelect
            id={id}
            className="w-48"
            value={values.statut}
            onChange={(e) => onChange({ statut: e.target.value })}
          >
            <option value="">{t.filterAll}</option>
            {Object.entries(statusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
      <Toggle
        label={t.filterOverdue}
        checked={values.en_retard}
        onChange={(en_retard) => onChange({ en_retard })}
      />
      {role === "AUDITE" && view === "actions" && (
        <Toggle
          label={t.filterMine}
          checked={values.mine}
          onChange={(mine) => onChange({ mine })}
        />
      )}
      <Button type="button" variant="ghost" size="sm" className="mb-1" onClick={onReset}>
        {t.filtersReset}
      </Button>
    </form>
  );
}
