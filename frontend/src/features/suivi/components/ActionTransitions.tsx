import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
import { useAuth } from "@/auth/useAuth";
import { MotifDialog } from "@/features/missions/components/MotifDialog";
import { fr } from "@/i18n/fr";
import { useActionTransition } from "../api";
import { fieldErrorsOf, generalErrorOf } from "../serverErrors";
import type { ActionSuivie, TransitionKind } from "../types";

const t = fr.suiviRegistre;

type Code =
  | "DEMARRER"
  | "DECLARER_REALISEE"
  | "PROPOSER_ABANDON"
  | "VERIFIER"
  | "REJETER"
  | "CLOTURER"
  | "ACCEPTER_ABANDON"
  | "ROUVRIR";

/** Codes du serveur (`actions_possibles`) affichés ici, dans l'ordre d'affichage. */
const TRANSITIONS: {
  code: Code;
  kind: TransitionKind;
  label: string;
  variant: "default" | "outline";
}[] = [
  { code: "DEMARRER", kind: "start", label: t.start, variant: "default" },
  { code: "DECLARER_REALISEE", kind: "declare-done", label: t.declareDone, variant: "default" },
  { code: "VERIFIER", kind: "verify", label: t.verify, variant: "default" },
  { code: "CLOTURER", kind: "close", label: t.close, variant: "default" },
  { code: "ACCEPTER_ABANDON", kind: "accept-abandon", label: t.acceptAbandon, variant: "outline" },
  {
    code: "PROPOSER_ABANDON",
    kind: "propose-abandon",
    label: t.proposeAbandon,
    variant: "outline",
  },
  { code: "REJETER", kind: "reject", label: t.reject, variant: "outline" },
  { code: "ROUVRIR", kind: "reopen", label: t.reopen, variant: "outline" },
];

const MOTIF_DIALOGS: Partial<
  Record<Code, { title: string; description: string; confirm: string }>
> = {
  PROPOSER_ABANDON: {
    title: t.proposeAbandonTitle,
    description: t.proposeAbandonDescription,
    confirm: t.proposeAbandon,
  },
  REJETER: { title: t.rejectTitle, description: t.rejectDescription, confirm: t.reject },
  ROUVRIR: { title: t.reopenTitle, description: t.reopenDescription, confirm: t.reopen },
  ACCEPTER_ABANDON: {
    title: t.acceptAbandonTitle,
    description: t.acceptAbandonDescription,
    confirm: t.acceptAbandon,
  },
};

const EXECUTING: Code[] = ["DEMARRER", "DECLARER_REALISEE", "PROPOSER_ABANDON"];

type DeclareProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (commentaire: string) => Promise<unknown>;
};

/** « Déclarer réalisée » : commentaire obligatoire, erreurs serveur liées au champ. */
function DeclareDialog({ open, onOpenChange, onSubmit }: DeclareProps) {
  const [text, setText] = useState("");
  const [fieldError, setFieldError] = useState<string>();
  const [general, setGeneral] = useState<string>();
  const [pending, setPending] = useState(false);
  const field = useRef<HTMLTextAreaElement>(null);
  const [focusTick, setFocusTick] = useState(0);

  useEffect(() => {
    if (focusTick > 0) field.current?.focus();
  }, [focusTick]);

  function change(next: boolean) {
    if (pending) return;
    if (!next) {
      setText("");
      setFieldError(undefined);
      setGeneral(undefined);
    }
    onOpenChange(next);
  }

  async function submit() {
    const trimmed = text.trim();
    setGeneral(undefined);
    if (!trimmed) {
      setFieldError(t.declareCommentRequired);
      setFocusTick((n) => n + 1);
      return;
    }
    setPending(true);
    setFieldError(undefined);
    try {
      await onSubmit(trimmed);
      setPending(false);
      change(false);
    } catch (e) {
      const fields = fieldErrorsOf(e);
      setFieldError(fields.commentaire);
      setGeneral(generalErrorOf(e));
      if (fields.commentaire) setFocusTick((n) => n + 1);
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.declareTitle}</DialogTitle>
          <DialogDescription>{t.declareDescription}</DialogDescription>
        </DialogHeader>
        <FormField label={t.declareComment} error={fieldError}>
          {(props) => (
            <Textarea
              {...props}
              ref={field}
              rows={4}
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          )}
        </FormField>
        {general && (
          <p role="alert" className={ALERT_CLASS}>
            {general}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" disabled={pending} onClick={() => change(false)}>
            {fr.common.cancel}
          </Button>
          <Button type="button" disabled={pending} onClick={() => void submit()}>
            {t.declareConfirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Boutons de transition d'après `actions_possibles` du serveur ; aucun droit n'est recalculé ici. */
export function ActionTransitions({ action }: { action: ActionSuivie }) {
  const { me } = useAuth();
  const transition = useActionTransition();
  const [dialog, setDialog] = useState<Code | null>(null);
  const [error, setError] = useState<string>();
  const needId = useId();

  const possible = new Set(action.actions_possibles);
  const available = TRANSITIONS.filter((item) => possible.has(item.code));
  const noProof = action.nombre_preuves === 0;
  const onBehalf = me?.role === "RAI" && EXECUTING.some((code) => possible.has(code));

  function run(kind: TransitionKind, text?: string) {
    return transition.mutateAsync({ id: action.id, kind, text, missionId: action.mission.id });
  }

  async function direct(kind: TransitionKind) {
    setError(undefined);
    try {
      await run(kind);
    } catch (e) {
      setError(generalErrorOf(e) ?? t.transitionError);
    }
  }

  function open(item: (typeof TRANSITIONS)[number]) {
    setError(undefined);
    if (item.code === "DEMARRER" || item.code === "VERIFIER" || item.code === "CLOTURER") {
      void direct(item.kind);
    } else {
      setDialog(item.code);
    }
  }

  const motif = dialog ? MOTIF_DIALOGS[dialog] : undefined;
  const motifKind = TRANSITIONS.find((item) => item.code === dialog)?.kind;

  return (
    <section
      aria-labelledby="action-transitions-title"
      className="rounded-lg border border-border p-5"
    >
      <h2 id="action-transitions-title" className="mb-3 text-base font-semibold">
        {t.transitionsTitle}
      </h2>
      {onBehalf && (
        <p className="mb-3 text-sm text-text-muted">
          {t.onBehalfOf.replace("{name}", action.responsable.nom_complet)}
        </p>
      )}
      {available.length === 0 ? (
        <p className="text-sm text-text-muted">{t.noTransitions}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {available.map((item) => {
            const blocked = item.code === "DECLARER_REALISEE" && noProof;
            return (
              <Button
                key={item.code}
                type="button"
                variant={item.variant}
                disabled={blocked || transition.isPending}
                aria-describedby={blocked ? needId : undefined}
                onClick={() => open(item)}
              >
                {item.label}
              </Button>
            );
          })}
        </div>
      )}
      {possible.has("DECLARER_REALISEE") && noProof && (
        <p id={needId} className="mt-2 text-sm text-text-muted">
          {t.needEvidence}
        </p>
      )}
      {error && (
        <p role="alert" className={`${ALERT_CLASS} mt-3`}>
          {error}
        </p>
      )}
      <DeclareDialog
        open={dialog === "DECLARER_REALISEE"}
        onOpenChange={(o) => !o && setDialog(null)}
        onSubmit={(commentaire) => run("declare-done", commentaire)}
      />
      {motif && motifKind && (
        <MotifDialog
          open
          onOpenChange={(o) => !o && setDialog(null)}
          title={motif.title}
          description={motif.description}
          confirmLabel={motif.confirm}
          onSubmit={(text) => run(motifKind, text)}
        />
      )}
    </section>
  );
}
