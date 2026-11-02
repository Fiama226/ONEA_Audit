import { useEffect, useId, useRef, useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { fr } from "@/i18n/fr";
import { useAssign, useDefaultAuditees, useReplaceChief } from "../api";
import { ROLE_MISSION_LABELS } from "../labels";
import type { Mission, RoleMission } from "../types";
import { UserPicker } from "./UserPicker";

const m = fr.missionPilotage;
const ROLES = Object.keys(ROLE_MISSION_LABELS) as RoleMission[];

type Props = {
  mission: Mission;
  /** `replace-chief` : un seul nouveau chef, choisi parmi les auditeurs. */
  mode: "assign" | "replace-chief";
  onClose: () => void;
};

/** Affectation de personnes à la mission (ou remplacement du chef) ; le serveur reste seul juge. */
export function AssignDialog({ mission, mode, onClose }: Props) {
  const assign = useAssign();
  const replace = useReplaceChief();
  const defaults = useDefaultAuditees(mode === "assign" ? mission.id : undefined);
  const [role, setRole] = useState<RoleMission>(mode === "assign" ? "AUDITEUR" : "CHEF_MISSION");
  // null : l'utilisateur n'a rien touché, les audités par défaut restent pré-cochés.
  const [picked, setPicked] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [managerChecked, setManagerChecked] = useState(false);
  const [managerError, setManagerError] = useState<string | null>(null);
  const managerRef = useRef<HTMLButtonElement>(null);
  const managerId = useId();
  // Après le rendu : la case est désactivée pendant l'envoi et ne peut pas recevoir le focus avant.
  useEffect(() => {
    if (managerError !== null) managerRef.current?.focus();
  }, [managerError]);
  const [pending, setPending] = useState(false);
  // Personnes déjà affectées lors d'une tentative partielle : jamais renvoyées au nouvel essai.
  const done = useRef<Set<string>>(new Set());

  const assigned = mission.equipe.map((a) => String(a.utilisateur));
  const defaultIds = (defaults.data ?? [])
    .map((u) => String(u.id))
    .filter((id) => !assigned.includes(id));
  const selected = picked ?? (role === "AUDITE" ? defaultIds : []);
  const single = mode === "replace-chief" || role === "CHEF_MISSION" || role === "SUPERVISEUR";
  const pickerRole = role === "AUDITE" ? "AUDITE" : "AUDITEUR";
  // Un seul responsable par direction : la case ne s'applique qu'à une personne à la fois.
  const managerAvailable = role === "AUDITE" && mode === "assign";
  const managerEnabled = managerAvailable && selected.length === 1;
  const manager = managerEnabled && managerChecked;

  async function submit() {
    if (selected.length === 0) {
      setError(m.assignNobody);
      return;
    }
    setPending(true);
    setError(null);
    setManagerError(null);
    try {
      if (mode === "replace-chief") {
        await replace.mutateAsync({ id: mission.id, utilisateur: Number(selected[0]) });
      } else {
        for (const id of selected) {
          if (done.current.has(id)) continue;
          await assign.mutateAsync({
            mission: mission.id,
            utilisateur: Number(id),
            role_mission: role,
            responsable_entite: manager,
          });
          done.current.add(id);
        }
      }
      onClose();
    } catch (e) {
      if (isApiError(e)) {
        const { responsable_entite: managerMessages, ...others } = e.errors;
        if (managerMessages) {
          setManagerError(managerMessages.join(" "));
        }
        const general = managerMessages ? [] : [e.detail];
        setError([...general, ...Object.values(others).flat()].join(" ") || null);
      } else {
        setError(fr.errors.generic);
      }
      setPending(false);
    }
  }

  const replacing = mode === "replace-chief";
  return (
    <AlertDialog
      open
      onOpenChange={(next) => {
        if (!next && !pending) onClose();
      }}
    >
      <AlertDialogContent className="max-h-[90vh] overflow-y-auto">
        <AlertDialogHeader>
          <AlertDialogTitle>{replacing ? m.replaceTitle : m.assignTitle}</AlertDialogTitle>
          <AlertDialogDescription>
            {replacing ? m.replaceText : m.assignDefaultsHelp}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {!replacing && (
          <div className="grid gap-1.5">
            <Label htmlFor="assign-role">{m.assignRole}</Label>
            <NativeSelect
              id="assign-role"
              value={role}
              onChange={(e) => {
                setRole(e.target.value as RoleMission);
                setPicked(null);
              }}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_MISSION_LABELS[r]}
                </option>
              ))}
            </NativeSelect>
          </div>
        )}
        <UserPicker
          role={pickerRole}
          label={pickerRole === "AUDITE" ? m.assignPickerAudite : m.assignPickerAuditeur}
          value={selected}
          single={single}
          onChange={setPicked}
          exclude={assigned}
        />
        {managerAvailable && (
          <div className="grid gap-1.5">
            <div className="flex items-center gap-2">
              <Checkbox
                id={managerId}
                ref={managerRef}
                checked={manager}
                disabled={!managerEnabled || pending}
                onCheckedChange={(value) => setManagerChecked(value === true)}
                aria-invalid={managerError !== null}
                aria-describedby={[`${managerId}-help`, managerError ? `${managerId}-error` : null]
                  .filter(Boolean)
                  .join(" ")}
              />
              <Label htmlFor={managerId}>{m.entityManager}</Label>
            </div>
            <p id={`${managerId}-help`} className="text-xs text-text-muted">
              {managerEnabled ? m.entityManagerHelp : m.entityManagerSingleOnly}
            </p>
            {managerError && (
              <p id={`${managerId}-error`} role="alert" className="text-sm text-destructive">
                {managerError}
              </p>
            )}
          </div>
        )}
        {error && (
          <p role="alert" className={ALERT_CLASS}>
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>{fr.common.cancel}</AlertDialogCancel>
          <Button type="button" disabled={pending} onClick={() => void submit()}>
            {replacing ? m.replaceConfirm : m.assignConfirm}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
