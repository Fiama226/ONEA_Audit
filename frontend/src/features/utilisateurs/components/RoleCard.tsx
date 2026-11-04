import { TriangleAlert } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { isApiError } from "@/api/errors";
import { useAccountRights } from "@/auth/useAccountRights";
import { FormField } from "@/components/form/FormField";
import { NativeSelect } from "@/components/form/NativeSelect";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
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
  const [confirming, setConfirming] = useState(false);
  const selectRef = useRef<HTMLSelectElement>(null);
  // Seul un administrateur attribue le rôle Administrateur ; le rôle actuel n'est pas proposé.
  const choices = assignableRoles(isAdmin).filter((r) => r !== account.role);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (role === "") return;
    setError(undefined);
    setDone(false);
    setConfirming(true);
  }

  async function apply() {
    if (role === "") return;
    setConfirming(false);
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

  /** Le bouton déclencheur se désactive après le changement : le focus revient au sélecteur. */
  function onCloseAutoFocus(event: Event) {
    event.preventDefault();
    selectRef.current?.focus();
  }

  const confirmText = t.roleConfirmText
    .replace("{from}", ROLE_LABELS[account.role])
    .replace("{to}", role === "" ? "" : ROLE_LABELS[role]);

  return (
    <form onSubmit={onSubmit} noValidate className="grid gap-3 print:hidden">
      <div className="max-w-sm">
        <FormField label={t.newRole} error={error} announceError>
          {(p) => (
            <NativeSelect
              {...p}
              ref={selectRef}
              value={role}
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
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent onCloseAutoFocus={onCloseAutoFocus}>
          <AlertDialogHeader>
            <AlertDialogTitle>{`${t.roleConfirmTitle}${account.nom_complet} ?`}</AlertDialogTitle>
            <AlertDialogDescription>{confirmText}</AlertDialogDescription>
          </AlertDialogHeader>
          {role === "ADMIN" && (
            <p className="flex gap-2 rounded-md border border-warning/50 p-3 text-sm text-warning-text">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>{t.roleConfirmAdmin}</span>
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{fr.common.cancel}</AlertDialogCancel>
            <Button
              type="button"
              variant={role === "ADMIN" ? "destructive" : "default"}
              onClick={() => void apply()}
            >
              {t.roleConfirm}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </form>
  );
}
