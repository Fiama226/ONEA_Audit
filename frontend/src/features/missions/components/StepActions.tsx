import { useState } from "react";
import { isApiError } from "@/api/errors";
import { ALERT_CLASS } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";
import { fr } from "@/i18n/fr";
import { useStepAction, type StepAction } from "../api";
import { ACTION_LABELS } from "../labels";
import type { ActionEtape, Etape } from "../types";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { MotifDialog } from "./MotifDialog";

const m = fr.missionEtapes;

/** Actions sans saisie : l'API est appelée directement. */
const DIRECT: Partial<Record<ActionEtape, StepAction>> = {
  DEMARRER: "start",
  TERMINER: "complete",
  RETABLIR: "restore",
};

/** Actions qui exigent un motif. */
const WITH_MOTIF: Partial<
  Record<ActionEtape, { action: StepAction; title: string; text: string }>
> = {
  RENVOYER: { action: "return", title: m.returnTitle, text: m.returnText },
  ROUVRIR: { action: "reopen", title: m.reopenTitle, text: m.reopenText },
  NON_APPLICABLE: {
    action: "not-applicable",
    title: m.notApplicableTitle,
    text: m.notApplicableText,
  },
};

/** Ordre d'affichage des boutons ; chacun n'apparaît que si le serveur l'autorise. */
const ORDER: ActionEtape[] = [
  "DEMARRER",
  "TERMINER",
  "VALIDER",
  "RENVOYER",
  "ROUVRIR",
  "NON_APPLICABLE",
  "RETABLIR",
];

type Failure = { detail: string; livrables: string[] };

/** Boutons d'action d'une étape, uniquement ceux de `actions_possibles` (jamais recalculés). */
export function StepActions({ step }: { step: Etape }) {
  const run = useStepAction();
  const [dialog, setDialog] = useState<ActionEtape | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const actions = ORDER.filter((a) => step.actions_possibles.includes(a));
  if (actions.length === 0) return null;

  async function direct(action: StepAction) {
    setFailure(null);
    try {
      await run.mutateAsync({ id: step.id, action });
    } catch (e) {
      setFailure(
        isApiError(e)
          ? { detail: e.detail, livrables: e.errors.livrables ?? [] }
          : { detail: fr.errors.generic, livrables: [] },
      );
    }
  }

  const motif = dialog ? WITH_MOTIF[dialog] : undefined;

  return (
    <div className="grid gap-3 print:hidden">
      <div role="group" aria-label={m.actionsLabel} className="flex flex-wrap gap-2">
        {actions.map((a) => {
          const action = DIRECT[a];
          return (
            <Button
              key={a}
              type="button"
              variant={
                a === "VALIDER" || a === "TERMINER" || a === "DEMARRER" ? "default" : "outline"
              }
              disabled={run.isPending}
              onClick={() => (action ? void direct(action) : setDialog(a))}
            >
              {ACTION_LABELS[a]}
            </Button>
          );
        })}
      </div>
      {failure && (
        <div role="alert" className={ALERT_CLASS}>
          <p>{failure.livrables.length > 0 ? m.livrablesError : failure.detail}</p>
          {failure.livrables.length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {failure.livrables.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      <ConfirmActionDialog
        open={dialog === "VALIDER"}
        onOpenChange={(open) => !open && setDialog(null)}
        title={m.validateTitle}
        text={m.validateText.replace("{romain}", step.romain)}
        confirmLabel={ACTION_LABELS.VALIDER}
        onConfirm={() => run.mutateAsync({ id: step.id, action: "validate" })}
      />
      {motif && dialog && (
        <MotifDialog
          open
          onOpenChange={(open) => !open && setDialog(null)}
          title={motif.title}
          description={motif.text}
          confirmLabel={ACTION_LABELS[dialog]}
          onSubmit={(text) => run.mutateAsync({ id: step.id, action: motif.action, motif: text })}
        />
      )}
    </div>
  );
}
