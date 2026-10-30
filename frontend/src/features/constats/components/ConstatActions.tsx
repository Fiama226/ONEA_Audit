import { zodResolver } from "@hookform/resolvers/zod";
import { Printer } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { applyApiErrors } from "@/api/formErrors";
import { ALERT_CLASS, FormField } from "@/components/form/FormField";
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
import { Textarea } from "@/components/ui/textarea";
import { fr } from "@/i18n/fr";
import { useDeleteFinding, useFindingAction } from "../api";
import { CONSTAT_ACTION_LABELS } from "../labels";
import { motifSchema } from "../schemas/constat";
import type { Constat, ConstatAction } from "../types";
import { ReponseDialog } from "./ReponseDialog";

const t = fr.constatsUi;

/** Codes de `actions_possibles` (serveur) -> route de transition. */
const TRANSITIONS: Record<string, ConstatAction> = {
  SOUMETTRE: "submit",
  VALIDER: "validate",
  RENVOYER: "return",
  ROUVRIR: "reopen",
};

type Props = {
  constat: Constat;
  /** Reçoit l'erreur d'une action ; retourne le message général à afficher (ou null si posé sur un champ). */
  onError: (error: unknown) => string | null;
  onDeleted: () => void;
};

/** Boutons des actions que le serveur autorise (`actions_possibles`) ; rien n'est déduit du rôle. */
export function ConstatActions({ constat, onError, onDeleted }: Props) {
  const action = useFindingAction();
  const remove = useDeleteFinding();
  const [message, setMessage] = useState<string | null>(null);
  const [returning, setReturning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [responding, setResponding] = useState(false);
  const possible = constat.actions_possibles;

  async function run(name: ConstatAction) {
    setMessage(null);
    try {
      await action.mutateAsync({ id: constat.id, missionId: constat.mission, action: name });
    } catch (e) {
      setMessage(onError(e));
    }
  }

  async function confirmDelete() {
    setMessage(null);
    try {
      await remove.mutateAsync({ id: constat.id, missionId: constat.mission });
      setDeleting(false);
      onDeleted();
    } catch (e) {
      setDeleting(false);
      setMessage(onError(e));
    }
  }

  const transitions = possible.filter((a) => a in TRANSITIONS && a !== "RENVOYER");
  return (
    <section aria-label={t.actionsTitle} className="flex flex-wrap items-center gap-2 print:hidden">
      {message && (
        <p role="alert" className={`${ALERT_CLASS} basis-full`}>
          {message}
        </p>
      )}
      {transitions.map((a) => {
        const name = TRANSITIONS[a] as ConstatAction;
        return (
          <Button key={a} type="button" disabled={action.isPending} onClick={() => void run(name)}>
            {CONSTAT_ACTION_LABELS[name]}
          </Button>
        );
      })}
      {possible.includes("RENVOYER") && (
        <Button type="button" variant="outline" onClick={() => setReturning(true)}>
          {CONSTAT_ACTION_LABELS.return}
        </Button>
      )}
      {possible.includes("REPONDRE") && (
        <Button type="button" onClick={() => setResponding(true)}>
          {t.respond}
        </Button>
      )}
      {possible.includes("SUPPRIMER") && (
        <Button type="button" variant="destructive" onClick={() => setDeleting(true)}>
          {t.actionDelete}
        </Button>
      )}
      <Button type="button" variant="outline" onClick={() => window.print()}>
        <Printer aria-hidden />
        {t.print}
      </Button>

      <ReturnDialog
        open={returning}
        onOpenChange={setReturning}
        onSubmit={async (motif) => {
          await action.mutateAsync({
            id: constat.id,
            missionId: constat.mission,
            action: "return",
            motif,
          });
          setReturning(false);
        }}
      />
      <ReponseDialog constat={constat} open={responding} onOpenChange={setResponding} />
      <AlertDialog open={deleting} onOpenChange={setDeleting}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t.deleteTitle}</AlertDialogTitle>
            <AlertDialogDescription>
              {t.deleteDescription.replace("{reference}", constat.reference)}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{fr.common.cancel}</AlertDialogCancel>
            <Button
              type="button"
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => void confirmDelete()}
            >
              {fr.common.delete}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

function ReturnDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (motif: string) => Promise<void>;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<{ motif: string }>({
    resolver: zodResolver(motifSchema),
    defaultValues: { motif: "" },
  });

  async function submit(values: { motif: string }) {
    setFormError(null);
    try {
      await onSubmit(values.motif);
      reset();
    } catch (e) {
      setFormError(applyApiErrors(e, setError, ["motif"]));
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <form onSubmit={(e) => void handleSubmit(submit)(e)} noValidate className="grid gap-4">
          <AlertDialogHeader>
            <AlertDialogTitle>{t.returnTitle}</AlertDialogTitle>
            <AlertDialogDescription>{t.returnMotif}</AlertDialogDescription>
          </AlertDialogHeader>
          {formError && (
            <p role="alert" className={ALERT_CLASS}>
              {formError}
            </p>
          )}
          <FormField label={t.returnMotif} error={errors.motif?.message}>
            {(p) => <Textarea {...p} rows={3} {...register("motif")} />}
          </FormField>
          <AlertDialogFooter>
            <AlertDialogCancel type="button">{fr.common.cancel}</AlertDialogCancel>
            <Button type="submit" disabled={isSubmitting}>
              {t.returnConfirm}
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  );
}
