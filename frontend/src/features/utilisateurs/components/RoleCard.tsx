import { useState, type FormEvent } from "react";
import { isApiError } from "@/api/errors";
import { useAccountRights } from "@/auth/useAccountRights";
import { FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fr } from "@/i18n/fr";
import { useChangeRole } from "../api";
import { assignableRoles, ROLE_LABELS } from "../labels";
import type { CompteUtilisateur, Role } from "../types";

const t = fr.utilisateurs.fiche;

/** Rôle du compte ; changement réservé au droit « changer les rôles » (`actions.changer_role`). */
export function RoleCard({ account }: { account: CompteUtilisateur }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t.roleTitle}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <p className="font-medium">{ROLE_LABELS[account.role]}</p>
        <p className="text-text-muted">{t.roleNote}</p>
        {account.actions.changer_role && <ChangeRoleForm account={account} />}
      </CardContent>
    </Card>
  );
}

function ChangeRoleForm({ account }: { account: CompteUtilisateur }) {
  const { isAdmin } = useAccountRights();
  const mutation = useChangeRole();
  const [role, setRole] = useState<Role | "">("");
  const [error, setError] = useState<string | undefined>(undefined);
  const [done, setDone] = useState(false);
  // Seul un administrateur attribue le rôle Administrateur ; le rôle actuel n'est pas proposé.
  const choices = assignableRoles(isAdmin).filter((r) => r !== account.role);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (role === "") return;
    setError(undefined);
    setDone(false);
    try {
      await mutation.mutateAsync({ id: account.id, role });
      setRole("");
      setDone(true);
    } catch (e) {
      if (!isApiError(e)) return setError(fr.errors.generic);
      const messages = e.errors.role ?? [];
      setError(messages.length > 0 ? messages.join(" ") : e.detail);
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} noValidate className="grid gap-3 print:hidden">
      <div className="max-w-sm">
        <FormField label={t.newRole} error={error} announceError>
          {(p) => (
            <NativeSelect
              {...p}
              value={role}
              disabled={mutation.isPending}
              onChange={(e) => {
                setRole(e.target.value as Role | "");
                setError(undefined);
                setDone(false);
              }}
            >
              <option value="">{fr.utilisateurs.creation.rolePlaceholder}</option>
              {choices.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
      </div>
      <div>
        <Button type="submit" variant="outline" disabled={role === "" || mutation.isPending}>
          {mutation.isPending ? t.changingRole : t.changeRole}
        </Button>
      </div>
      <p role="status" className="text-success-text">
        {done ? t.roleChanged : ""}
      </p>
    </form>
  );
}
