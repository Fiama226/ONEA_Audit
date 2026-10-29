import { useId, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ALERT_CLASS } from "@/components/form/FormField";
import { ListIncompleteAlert } from "@/components/ListIncompleteAlert";
import { fr } from "@/i18n/fr";
import { useAllUsers } from "../api";
import type { RoleEnum, UtilisateurResume } from "../types";

type Props = {
  /** Rôle recherché ; absent = tous les rôles. */
  role?: RoleEnum;
  /** Identifiants des utilisateurs sélectionnés (sous forme de texte). */
  value: string[];
  onChange: (value: string[]) => void;
  exclude?: string[];
  label: string;
  /** Message d'erreur du serveur ou de validation, affiché sous la liste. */
  error?: string;
  /** Utilisateurs déjà enregistrés (pour nommer un compte devenu inactif). */
  known?: UtilisateurResume[];
};

/**
 * Sélecteur d'utilisateurs actifs (d'un rôle, ou de tous les rôles si `role` est absent) :
 * charge toute la liste et filtre localement. Un utilisateur déjà sélectionné mais absent de la
 * liste (compte désactivé) reste affiché et décochable, pour ne jamais bloquer une modification.
 */
export function UserPicker({
  role,
  value,
  onChange,
  exclude = [],
  label,
  error,
  known = [],
}: Props) {
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

  const complete = users.data !== undefined && users.data.count === users.data.results.length;
  const activeIds = new Set((users.data?.results ?? []).map((u) => String(u.id)));
  const inactive = complete
    ? value.filter((id) => !activeIds.has(id) && !exclude.includes(id))
    : [];

  function inactiveName(id: string): string {
    const found = known.find((u) => String(u.id) === id);
    const name = found ? found.nom_complet : fr.missionTravaux.inactiveUser.replace("{id}", id);
    return fr.missionTravaux.inactiveAccount.replace("{name}", name);
  }

  function toggle(id: string, checked: boolean) {
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
          {inactive.map((id) => {
            const inputId = `${searchId}-${id}`;
            return (
              <li key={id} className="flex items-center gap-2 px-3 py-2 text-sm">
                <Checkbox
                  id={inputId}
                  checked
                  onCheckedChange={() => onChange(value.filter((v) => v !== id))}
                />
                <Label htmlFor={inputId} className="font-normal text-text-muted">
                  {inactiveName(id)}
                </Label>
              </li>
            );
          })}
          {visible.length === 0 && inactive.length === 0 && !users.isError && (
            <li className="p-3 text-sm text-text-muted">{fr.missions.pickerNone}</li>
          )}
          {visible.map((u) => {
            const id = String(u.id);
            const inputId = `${searchId}-${id}`;
            return (
              <li key={id} className="flex items-center gap-2 px-3 py-2 text-sm">
                <Checkbox
                  id={inputId}
                  checked={value.includes(id)}
                  onCheckedChange={(checked) => toggle(id, checked === true)}
                />
                <Label htmlFor={inputId} className="font-normal">
                  {u.nom_complet}
                  {u.fonction && <span className="text-text-muted"> · {u.fonction}</span>}
                </Label>
              </li>
            );
          })}
        </ul>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <p className="text-xs text-text-muted" aria-live="polite">
        {fr.missions.pickerSelected.replace("{count}", String(value.length))}
      </p>
    </fieldset>
  );
}
