import { MoreHorizontal } from "lucide-react";
import { Fragment, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fr } from "@/i18n/fr";
import { useDeleteMission, useMissionTransition, type MissionAction } from "../api";
import type { DroitsMission, Mission } from "../types";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { MotifDialog } from "./MotifDialog";

const m = fr.missionPilotage;

type Dialog = "plan" | "launch" | "suspend" | "resume" | "cancel" | "delete";

type ActionDef = { right: keyof DroitsMission; label: string; destructive?: boolean } & (
  { kind: "edit" } | { kind: "order" } | { kind: "dialog"; dialog: Dialog }
);

/** Ordre d'affichage ; chaque entrée n'apparaît que si le serveur accorde le droit correspondant. */
const ACTIONS: ActionDef[] = [
  { right: "modifier", label: m.actionEdit, kind: "edit" },
  { right: "planifier", label: m.actionPlan, kind: "dialog", dialog: "plan" },
  { right: "lancer", label: m.actionLaunch, kind: "dialog", dialog: "launch" },
  { right: "emettre_ordre", label: m.actionIssueOrder, kind: "order" },
  { right: "suspendre", label: m.actionSuspend, kind: "dialog", dialog: "suspend" },
  { right: "reprendre", label: m.actionResume, kind: "dialog", dialog: "resume" },
  { right: "annuler", label: m.actionCancel, kind: "dialog", dialog: "cancel", destructive: true },
  {
    right: "supprimer",
    label: m.actionDelete,
    kind: "dialog",
    dialog: "delete",
    destructive: true,
  },
];

const SIMPLE: Partial<Record<Dialog, { action: MissionAction; text: string; confirm: string }>> = {
  plan: { action: "plan", text: m.planText, confirm: m.confirmPlan },
  launch: { action: "launch", text: m.launchText, confirm: m.confirmLaunch },
  resume: { action: "resume", text: m.resumeText, confirm: m.confirmResume },
};

/** Menu des actions de cycle de vie ; chaque entrée vient de `mes_droits` (jamais recalculée). */
export function MissionActions({ mission }: { mission: Mission }) {
  const navigate = useNavigate();
  const transition = useMissionTransition();
  const remove = useDeleteMission();
  const [open, setOpen] = useState<Dialog | null>(null);
  const available = ACTIONS.filter((a) => mission.mes_droits[a.right]);
  if (available.length === 0) return null;

  const close = (next: boolean) => {
    if (!next) setOpen(null);
  };
  const simple = open ? SIMPLE[open] : undefined;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="outline" size="sm">
            <MoreHorizontal aria-hidden />
            {fr.missions.actionsMenu}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {available.map((a, i) => (
            <Fragment key={a.right}>
              {a.destructive && i > 0 && !available[i - 1]?.destructive && (
                <DropdownMenuSeparator />
              )}
              {a.kind === "edit" || a.kind === "order" ? (
                <DropdownMenuItem asChild>
                  <Link
                    to={
                      a.kind === "edit"
                        ? `/missions/${mission.id}/modifier`
                        : `/missions/${mission.id}/etapes/1`
                    }
                  >
                    {a.label}
                  </Link>
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  variant={a.destructive ? "destructive" : "default"}
                  onSelect={() => setOpen(a.dialog)}
                >
                  {a.label}
                </DropdownMenuItem>
              )}
            </Fragment>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {simple && (
        <ConfirmActionDialog
          open
          onOpenChange={close}
          title={ACTIONS.find((a) => a.kind === "dialog" && a.dialog === open)?.label ?? ""}
          text={simple.text}
          confirmLabel={simple.confirm}
          requireCheck={false}
          onConfirm={() => transition.mutateAsync({ id: mission.id, action: simple.action })}
        />
      )}
      {open === "suspend" && (
        <MotifDialog
          open
          onOpenChange={close}
          title={m.actionSuspend}
          description={m.suspendText}
          confirmLabel={m.confirmSuspend}
          onSubmit={(motif) =>
            transition.mutateAsync({ id: mission.id, action: "suspend", body: { motif } })
          }
        />
      )}
      {open === "cancel" && (
        <MotifDialog
          open
          onOpenChange={close}
          title={m.actionCancel}
          description={m.cancelText}
          confirmLabel={m.confirmCancel}
          onSubmit={(motif) =>
            transition.mutateAsync({ id: mission.id, action: "cancel", body: { motif } })
          }
        />
      )}
      {open === "delete" && (
        <ConfirmActionDialog
          open
          onOpenChange={close}
          title={m.actionDelete}
          text={m.deleteText}
          confirmLabel={m.confirmDelete}
          onConfirm={async () => {
            await remove.mutateAsync(mission.id);
            void navigate("/missions", { replace: true });
          }}
        />
      )}
    </>
  );
}
