import { useId, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ALERT_CLASS } from "@/components/form/FormField";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { fr } from "@/i18n/fr";
import { useAllUsers } from "../api";
import type { RoleEnum } from "../types";

type Props = {
  role: RoleEnum;
  /** Identifiants des utilisateurs sélectionnés (sous forme de texte). */
  value: string[];
  onChange: (value: string[]) => void;
  exclude?: string[];
  label: string;
  /** Choix unique : boutons radio au lieu de cases à cocher. */
  single?: boolean;
};

/** Sélecteur d'utilisateurs d'un rôle : charge toute la liste, filtre localement. */
export function UserPicker({ role, value, onChange, exclude = [], label, single = false }: Props) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const users = useAllUsers({ role });

  const needle = query.trim().toLowerCase();
  const visible = (users.data?.results ?? []).filter(
    (u) =>
      !exclude.includes(String(u.id)) &&
      (needle === "" ||
        u.nom_complet.toLowerCase().includes(needle) ||
        u.username.toLowerCase().includes(needle)),
  );

  function toggle(id: string, checked: boolean) {
    if (single) return onChange(checked ? [id] : []);
    onChange(checked ? [...value, id] : value.filter((v) => v !== id));
  }

  return (
    <fieldset className="grid gap-2">
      <legend className="text-sm font-medium">{label}</legend>
      <Label htmlFor={searchId} className="sr-only">
        {fr.missions.pickerSearch}
      </Label>
      <Input
        id={searchId}
        type="search"
        placeholder={fr.missions.pickerSearch}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {users.isError && (
        <p role="alert" className={ALERT_CLASS}>
          {fr.missions.pickerLoadError}
        </p>
      )}
      {users.data && (
        <ListIncompleteAlert count={users.data.count} loaded={users.data.results.length} />
      )}
      {users.isLoading ? (
        <p role="status" className="text-sm text-text-muted">
          {fr.common.loading}
        </p>
      ) : (
        <ul className="max-h-56 overflow-y-auto rounded-md border border-border">
          {visible.length === 0 && !users.isError && (
            <li className="p-3 text-sm text-text-muted">{fr.missions.pickerNone}</li>
          )}
          {visible.map((u) => {
            const id = String(u.id);
            const inputId = `${searchId}-${id}`;
            return (
              <li key={id} className="flex items-center gap-2 px-3 py-2 text-sm">
                {single ? (
                  <input
                    type="radio"
                    id={inputId}
                    name={`${searchId}-single`}
                    className="size-4 accent-primary"
                    checked={value.includes(id)}
                    onChange={() => toggle(id, true)}
                  />
                ) : (
                  <Checkbox
                    id={inputId}
                    checked={value.includes(id)}
                    onCheckedChange={(checked) => toggle(id, checked === true)}
                  />
                )}
                <Label htmlFor={inputId} className="font-normal">
                  {u.nom_complet}
                  {u.fonction && <span className="text-text-muted"> · {u.fonction}</span>}
                </Label>
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-xs text-text-muted" aria-live="polite">
        {fr.missions.pickerSelected.replace("{count}", String(value.length))}
      </p>
    </fieldset>
  );
}
