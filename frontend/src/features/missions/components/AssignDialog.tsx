import { useRef, useState } from "react";
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

  async function submit() {
    if (selected.length === 0) {
      setError(m.assignNobody);
      return;
    }
    setPending(true);
    setError(null);
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
          });
          done.current.add(id);
        }
      }
      onClose();
    } catch (e) {
      setError(
        isApiError(e) ? [e.detail, ...Object.values(e.errors).flat()].join(" ") : fr.errors.generic,
      );
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
